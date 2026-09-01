"""Boar Label Tool - 野猪标注修正 Web 服务"""

from flask import Flask, jsonify, request, send_from_directory
from pathlib import Path
import json
import shutil

app = Flask(__name__)
APP_PATH = Path(__file__).parent
PROJECT_PATH = Path("/home/zcy/Documents/project/boar_detection")

# ===== 数据集配置 =====
DATASETS = {
    "manual": {
        "label": "手工标注 (manual)",
        "path": str(PROJECT_PATH / "work/dataset"),
        "splits": ["train", "val"],
        "default_split": "train"
    },
    "auto_pukou1": {
        "label": "浦口4g-野猪1 (自动标注)",
        "path": str(PROJECT_PATH / "work/auto_label/pukou1"),
        "splits": ["labels"],
        "default_split": "labels"
    },
    "auto_pukou2": {
        "label": "浦口4g-野猪2 (自动标注)",
        "path": str(PROJECT_PATH / "work/auto_label/pukou2"),
        "splits": ["labels"],
        "default_split": "labels"
    },
    "auto_pukou3": {
        "label": "浦口4g-野猪3 (自动标注)",
        "path": str(PROJECT_PATH / "work/auto_label/pukou3"),
        "splits": ["labels"],
        "default_split": "labels"
    },
    "frames": {
        "label": "视频抽帧预标注 (frames)",
        "path": str(PROJECT_PATH / "work/auto_label_new/frames"),
        "splits": ["all"],
        "default_split": "all"
    },
    "pukou_img": {
        "label": "浦口未标注图预标注 (pukou_img)",
        "path": str(PROJECT_PATH / "work/auto_label_new/pukou_img"),
        "splits": ["all"],
        "default_split": "all"
    },
    "yewei_img": {
        "label": "野猪未标注图预标注 (yewei_img)",
        "path": str(PROJECT_PATH / "work/auto_label_new/yewei_img"),
        "splits": ["all"],
        "default_split": "all"
    },
    "merged": {
        "label": "合并数据集 (merged)",
        "path": str(PROJECT_PATH / "work/merged"),
        "splits": ["all"],
        "default_split": "all",
        "flat": True  # 扁平结构：images/ + labels/ 同级，无 train/val 子目录
    },
}

def get_dataset_path(dataset_id):
    cfg = DATASETS.get(dataset_id)
    return Path(cfg["path"]) if cfg else None

# ===== 前端 =====
@app.route("/")
def index():
    with open(str(APP_PATH / "label_tool.html"), "r", encoding="utf-8") as f:
        return f.read()

@app.route("/api/datasets")
def list_datasets():
    result = {}
    for k, v in DATASETS.items():
        result[k] = {
            "label": v["label"],
            "splits": v["splits"],
            "default_split": v["default_split"],
            "flat": v.get("flat", False)
        }
    return jsonify(result)

# ===== 图片列表 =====
@app.route("/api/images/<dataset_id>/<split>")
def list_images(dataset_id, split):
    path = get_dataset_path(dataset_id)
    if not path:
        return jsonify({"error": "unknown dataset"}), 404

    cfg = DATASETS.get(dataset_id, {})
    is_flat = cfg.get("flat", False)

    if is_flat:
        # merged 扁平结构：path/images/ 直接放图
        images_dir = path / "images"
        labels_dir = path / "labels"
    else:
        # 标准结构：path/{split}/images/
        images_dir = path / split / "images"
        labels_dir = path / split / "labels"

    if not images_dir.exists():
        return jsonify([])

    # 读取 split 文件（merged 用）。txt 里是绝对/相对图片路径，取文件名比较
    train_set = set()
    val_set = set()
    if is_flat:
        train_txt = path / "train.txt"
        val_txt = path / "val.txt"
        if train_txt.exists():
            with open(train_txt) as f:
                train_set = set(Path(line.strip()).name for line in f if line.strip())
        if val_txt.exists():
            with open(val_txt) as f:
                val_set = set(Path(line.strip()).name for line in f if line.strip())

    image_files = []
    for img_path in sorted(images_dir.iterdir()):
        if not img_path.is_file():
            continue
        ext = img_path.suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png", ".bmp"):
            continue
        label_path = labels_dir / (img_path.stem + ".txt")
        has_label = label_path.exists() and label_path.stat().st_size > 0

        item = {
            "name": img_path.name,
            "dataset": dataset_id,
            "split": split,
            "has_label": has_label,
            "label_size": label_path.stat().st_size if label_path.exists() else 0,
        }
        if is_flat:
            if img_path.name in train_set:
                item["split_tag"] = "train"
            elif img_path.name in val_set:
                item["split_tag"] = "val"
            else:
                item["split_tag"] = "unassigned"
        image_files.append(item)

    return jsonify(image_files)

# ===== 图片文件 =====
@app.route("/api/images/<dataset_id>/<split>/<image_name>")
def get_image(dataset_id, split, image_name):
    path = get_dataset_path(dataset_id)
    if not path:
        return jsonify({"error": "unknown dataset"}), 404

    cfg = DATASETS.get(dataset_id, {})
    if cfg.get("flat"):
        img_dir = path / "images"
    else:
        img_dir = path / split / "images"
    return send_from_directory(str(img_dir), image_name)

# ===== 标注读写 =====
def _dirs_for(dataset_id, split):
    """返回 (labels_dir, confs_file)。flat(merged) 结构 confs.json 在根，否则在 split/ 下"""
    path = get_dataset_path(dataset_id)
    cfg = DATASETS.get(dataset_id, {})
    if cfg.get("flat"):
        return path / "labels", path / "confs.json"
    return path / split / "labels", path / split / "confs.json"

def _load_confs(confs_file):
    if confs_file and confs_file.exists():
        try:
            return json.load(open(confs_file, encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_confs(confs_file, data):
    if not confs_file:
        return
    confs_file.parent.mkdir(parents=True, exist_ok=True)
    with open(confs_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

@app.route("/api/labels/<dataset_id>/<split>/<image_name>", methods=["GET", "POST"])
def handle_labels(dataset_id, split, image_name):
    path = get_dataset_path(dataset_id)
    if not path:
        return jsonify({"error": "unknown dataset"}), 404

    labels_dir, confs_file = _dirs_for(dataset_id, split)
    stem = Path(image_name).stem
    label_path = labels_dir / (stem + ".txt")

    if request.method == "GET":
        boxes = []
        if label_path.exists():
            confs = _load_confs(confs_file).get(stem)
            with open(label_path) as f:
                for i, line in enumerate(f):
                    line = line.strip()
                    if line:
                        parts = line.split()
                        box = {
                            "class_id": int(parts[0]),
                            "x_center": float(parts[1]),
                            "y_center": float(parts[2]),
                            "width": float(parts[3]),
                            "height": float(parts[4]),
                        }
                        box["conf"] = confs[i] if confs and i < len(confs) else None
                        boxes.append(box)
        return jsonify(boxes)
    else:
        boxes = request.json
        label_path.parent.mkdir(parents=True, exist_ok=True)
        confs = _load_confs(confs_file)
        conf_list = []
        with open(label_path, "w") as f:
            for box in boxes:
                f.write(f"{box['class_id']} {box['x_center']:.6f} {box['y_center']:.6f} {box['width']:.6f} {box['height']:.6f}\n")
                conf_list.append(box.get("conf"))
        confs[stem] = conf_list
        _save_confs(confs_file, confs)
        return jsonify({"success": True, "box_count": len(boxes)})

# ===== 类别 =====
@app.route("/api/classes")
def get_classes():
    return jsonify({"0": "boar"})

# ===== 审核：移到 merged =====
@app.route("/api/move_to_merged/<dataset_id>/<split>/<image_name>", methods=["POST"])
def move_to_merged(dataset_id, split, image_name):
    """将审核过的图片移动到 merged/images/ 和 merged/labels/"""
    src_path = get_dataset_path(dataset_id)
    dst_path = PROJECT_PATH / "work/merged"
    if not src_path:
        return jsonify({"error": "unknown dataset"}), 404

    stem = Path(image_name).stem
    src_images = src_path / split / "images"
    src_labels = src_path / split / "labels"

    # 找图片
    img_found = None
    for ext in [".jpg", ".JPG", ".jpeg", ".png", ".bmp"]:
        p = src_images / (stem + ext)
        if p.exists():
            img_found = p
            break
    if not img_found:
        return jsonify({"error": "image not found"}), 404

    dst_images = dst_path / "images"
    dst_labels = dst_path / "labels"
    dst_images.mkdir(parents=True, exist_ok=True)
    dst_labels.mkdir(parents=True, exist_ok=True)

    dst_img = dst_images / img_found.name
    if dst_img.exists():
        return jsonify({"error": f"文件已存在: {img_found.name}", "duplicate": True}), 409

    # 复制
    shutil.copy2(img_found, dst_img)
    src_label = src_labels / (stem + ".txt")
    dst_label = dst_labels / (stem + ".txt")
    if src_label.exists():
        shutil.copy2(src_label, dst_label)
    else:
        dst_label.write_text("")

    # 携带置信度：源 confs.json → merged confs.json
    _, src_confs = _dirs_for(dataset_id, split)
    src_cmap = _load_confs(src_confs)
    if stem in src_cmap:
        dst_confs = dst_path / "confs.json"
        dst_cmap = _load_confs(dst_confs)
        dst_cmap[stem] = src_cmap.pop(stem)
        _save_confs(dst_confs, dst_cmap)
        _save_confs(src_confs, src_cmap)

    # 从源目录删除（避免已审核的再出现）
    img_found.unlink(missing_ok=True)
    if src_label.exists():
        src_label.unlink(missing_ok=True)

    return jsonify({"success": True, "moved_to": str(dst_img)})


@app.route("/api/delete_image/<dataset_id>/<split>/<image_name>", methods=["POST"])
def delete_image(dataset_id, split, image_name):
    """删除图片及其标注文件"""
    path = get_dataset_path(dataset_id)
    if not path:
        return jsonify({"error": "unknown dataset"}), 404

    cfg = DATASETS.get(dataset_id, {})
    if cfg.get("flat"):
        img_dir = path / "images"
        label_dir = path / "labels"
    else:
        img_dir = path / split / "images"
        label_dir = path / split / "labels"

    stem = Path(image_name).stem

    # 删除图片
    deleted_img = False
    for ext in [".jpg", ".JPG", ".jpeg", ".png", ".bmp"]:
        p = img_dir / (stem + ext)
        if p.exists():
            p.unlink()
            deleted_img = True
            break

    # 删除标注
    deleted_label = False
    lp = label_dir / (stem + ".txt")
    if lp.exists():
        lp.unlink()
        deleted_label = True

    # 清理置信度旁路
    _, confs_file = _dirs_for(dataset_id, split)
    if confs_file and confs_file.exists():
        cmap = _load_confs(confs_file)
        if stem in cmap:
            del cmap[stem]
            _save_confs(confs_file, cmap)

    if not deleted_img:
        return jsonify({"error": "image not found"}), 404

    # 也清理 split 文件（如果是 merged 数据集）
    if dataset_id == "merged":
        merged_path = PROJECT_PATH / "work/merged"
        for tag in ("train", "val", "test"):
            sf = merged_path / f"{tag}.txt"
            if sf.exists():
                lines = [l for l in sf.read_text().splitlines() if l.strip() != image_name]
                sf.write_text("\n".join(lines) + ("\n" if lines else ""))

    return jsonify({"success": True, "deleted_image": deleted_img, "deleted_label": deleted_label})


# ===== Split 管理（merged 用） =====
ALL_SPLITS = ("train", "val", "test")

@app.route("/api/split/add/<split_tag>/<image_name>", methods=["POST"])
def add_to_split(split_tag, image_name):
    """将图片加入 train.txt / val.txt / test.txt"""
    merged_path = PROJECT_PATH / "work/merged"
    if split_tag not in ALL_SPLITS:
        return jsonify({"error": "invalid split"}), 400

    # 从其他 split 中移除
    for tag in ALL_SPLITS:
        if tag == split_tag:
            continue
        sf = merged_path / f"{tag}.txt"
        if sf.exists():
            lines = [l for l in sf.read_text().splitlines() if l.strip() != image_name]
            sf.write_text("\n".join(lines) + ("\n" if lines else ""))

    # 加入目标 split
    split_file = merged_path / f"{split_tag}.txt"
    names = set()
    if split_file.exists():
        with open(split_file) as f:
            names = set(line.strip() for line in f if line.strip())
    names.add(image_name)
    with open(split_file, "w") as f:
        for n in sorted(names):
            f.write(n + "\n")

    return jsonify({"success": True, "split": split_tag, "count": len(names)})

@app.route("/api/split/remove/<image_name>", methods=["POST"])
def remove_from_split(image_name):
    """从所有 split 中移除图片"""
    merged_path = PROJECT_PATH / "work/merged"
    for tag in ALL_SPLITS:
        sf = merged_path / f"{tag}.txt"
        if not sf.exists():
            continue
        lines = [l.strip() for l in sf.read_text().splitlines() if l.strip() and l.strip() != image_name]
        sf.write_text("\n".join(lines) + ("\n" if lines else ""))
    return jsonify({"success": True})

@app.route("/api/split/status")
def split_status():
    """返回 merged 数据集的划分统计"""
    merged_path = PROJECT_PATH / "work/merged"
    counts = {}
    for tag in ALL_SPLITS:
        sf = merged_path / f"{tag}.txt"
        if sf.exists():
            counts[tag] = len([l for l in sf.read_text().splitlines() if l.strip()])
        else:
            counts[tag] = 0

    total = 0
    if (merged_path / "images").exists():
        total = len([f for f in (merged_path / "images").iterdir()
                     if f.suffix.lower() in (".jpg",".jpeg",".png",".bmp")])

    return jsonify({
        "total": total,
        "train": counts["train"],
        "val": counts["val"],
        "test": counts["test"],
        "unassigned": total - counts["train"] - counts["val"] - counts["test"]
    })

# ===== 数据集统计 =====
@app.route("/api/dataset_stats/<dataset_id>/<split>")
def dataset_stats(dataset_id, split):
    path = get_dataset_path(dataset_id)
    if not path:
        return jsonify({"error": "unknown dataset"}), 404

    cfg = DATASETS.get(dataset_id, {})
    is_flat = cfg.get("flat", False)

    if is_flat:
        images_dir = path / "images"
        labels_dir = path / "labels"
    else:
        images_dir = path / split / "images"
        labels_dir = path / split / "labels"

    if not images_dir.exists():
        return jsonify({"total": 0, "labeled": 0, "empty": 0, "total_boxes": 0})

    total = labeled = empty = total_boxes = 0
    for f in images_dir.iterdir():
        if not f.is_file() or f.suffix.lower() not in (".jpg",".jpeg",".png",".bmp"):
            continue
        total += 1
        lp = labels_dir / (f.stem + ".txt")
        if lp.exists() and lp.stat().st_size > 0:
            labeled += 1
            total_boxes += sum(1 for line in open(lp) if line.strip())
        else:
            empty += 1

    return jsonify({"total": total, "labeled": labeled, "empty": empty, "total_boxes": total_boxes})


if __name__ == "__main__":
    print("🐗 Boar Label Tool starting...")
    print("   http://127.0.0.1:5000")
    for k, v in DATASETS.items():
        print(f"   {k}: {v['label']}")
    app.run(host="0.0.0.0", port=5000, debug=True)
