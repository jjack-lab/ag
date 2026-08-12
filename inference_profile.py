ACCURACY_IMGSZ = 960
MAX_DETECTIONS = 500


def build_predict_kwargs(conf, iou, class_id=-1, source_type="image"):
    kwargs = {
        "conf": conf,
        "iou": iou,
        "imgsz": ACCURACY_IMGSZ,
        "augment": source_type == "image",
        "max_det": MAX_DETECTIONS,
    }
    if class_id != -1:
        kwargs["classes"] = class_id
    return kwargs


def build_track_kwargs(conf, iou, class_id=-1):
    kwargs = {
        "persist": True,
        "conf": conf,
        "iou": iou,
        "imgsz": ACCURACY_IMGSZ,
        "augment": False,
        "max_det": MAX_DETECTIONS,
        "show": False,
    }
    if class_id != -1:
        kwargs["classes"] = class_id
    return kwargs
