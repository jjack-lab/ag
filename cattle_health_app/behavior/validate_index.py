"""Read-only validation of generated CVB manifests and real 16-frame clips."""
from __future__ import annotations
import argparse,csv,hashlib,json,os,tempfile,time
from collections import Counter
from pathlib import Path
import cv2

SPLITS=("train","val","test")

def _sha256(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda:source.read(1024*1024),b""): digest.update(chunk)
    return digest.hexdigest()

def validate_index(index_root,source_data_root,output=None):
    index_root=Path(index_root).resolve(); source_root=Path(source_data_root).resolve()
    started=time.perf_counter(); errors=[]; split_evidence={}; groups={}
    for split in SPLITS:
        manifest=index_root/f"{split}.csv"; counts=Counter(); selected={}; rows=0
        with manifest.open(encoding="utf-8",newline="") as source:
            for row in csv.DictReader(source):
                rows+=1
                try: label=int(row["label_id"])
                except (KeyError,ValueError): errors.append(f"{split}: invalid label at row {rows+1}"); continue
                counts[label]+=1; selected.setdefault(label,row)
                group=row.get("group_id","")
                previous=groups.setdefault(group,split)
                if group and previous!=split: errors.append(f"group leakage: {group}: {previous}/{split}")
        clips=0; frames=0
        for label,row in sorted(selected.items()):
            try: paths=json.loads(row["frame_paths"])
            except (KeyError,json.JSONDecodeError): errors.append(f"{split}/class {label}: invalid frame_paths"); continue
            if len(paths)!=16: errors.append(f"{split}/class {label}: expected 16 frames, got {len(paths)}"); continue
            for relative in paths:
                path=(source_root/relative).resolve()
                try: path.relative_to(source_root)
                except ValueError: errors.append(f"{split}/class {label}: path escape {relative}"); continue
                image=cv2.imread(str(path),cv2.IMREAD_COLOR); frames+=1
                if image is None or image.size==0: errors.append(f"{split}/class {label}: unreadable {relative}")
            clips+=1
        missing=[label for label in range(1,13) if not counts[label]]
        split_evidence[split]={"rows":rows,"class_counts":{str(i):counts[i] for i in range(1,13)},
            "missing_classes":missing,"clips_checked":clips,"frames_checked":frames,
            "manifest_sha256":_sha256(manifest)}
    quality=index_root/"quality_report.json"
    try: quality_report=json.loads(quality.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc:
        quality_report={}; errors.append(f"quality_report unreadable: {exc}")
    actual_leakage=any(error.startswith("group leakage") for error in errors)
    for split in SPLITS:
        actual=split_evidence[split]
        claimed_count=quality_report.get("per_split_counts",{}).get(split)
        if claimed_count!=actual["rows"]:
            errors.append(f"quality_report per_split_counts.{split}={claimed_count}, actual={actual['rows']}")
        claimed_missing=quality_report.get("per_split_missing_classes",{}).get(split)
        if claimed_missing!=actual["missing_classes"]:
            errors.append(f"quality_report per_split_missing_classes.{split} mismatch")
        claimed_classes=quality_report.get("per_split_class_counts",{}).get(split)
        if claimed_classes!=actual["class_counts"]:
            errors.append(f"quality_report per_split_class_counts.{split} mismatch")
    claimed_total=quality_report.get("accepted_count")
    actual_total=sum(item["rows"] for item in split_evidence.values())
    if claimed_total!=actual_total: errors.append(f"quality_report accepted_count={claimed_total}, actual={actual_total}")
    if quality_report.get("group_leakage")!=actual_leakage:
        errors.append(f"quality_report group_leakage={quality_report.get('group_leakage')}, actual={actual_leakage}")
    evidence={"success":not errors,"read_only":True,"splits":split_evidence,"errors":errors,
        "group_leakage":actual_leakage,"quality_claims_verified":not errors,
        "quality_report_sha256":_sha256(quality),"elapsed_seconds":round(time.perf_counter()-started,3)}
    if output:
        target=Path(output); target.parent.mkdir(parents=True,exist_ok=True)
        descriptor,name=tempfile.mkstemp(prefix=f".{target.name}.tmp-",dir=target.parent)
        temporary=Path(name)
        try:
            with os.fdopen(descriptor,"w",encoding="utf-8",newline="\n") as handle:
                json.dump(evidence,handle,ensure_ascii=False,indent=2); handle.write("\n")
                handle.flush(); os.fsync(handle.fileno())
            os.replace(temporary,target)
        except BaseException:
            try: os.close(descriptor)
            except OSError: pass
            temporary.unlink(missing_ok=True)
            raise
    return evidence

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-root",required=True,type=Path)
    parser.add_argument("--source-data-root",required=True,type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    evidence=validate_index(args.index_root,args.source_data_root,args.output)
    print(json.dumps(evidence,ensure_ascii=False,indent=2))
    return 0 if evidence["success"] else 1

if __name__=="__main__": raise SystemExit(main())
