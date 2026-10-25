"""Offline release manifest; reads locally, never imports SDK or writes PostgreSQL."""
import argparse
import hashlib
import json
from pathlib import Path
from company_import.validation import audit_file
from services.dataset_analysis import DatasetManifest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles",type=Path,required=True)
    parser.add_argument("--corpus-release",type=Path,required=True)
    parser.add_argument("--review-reference",required=True)
    parser.add_argument("--approve-dataset-combination",action="store_true")
    parser.add_argument("--payment-file",type=Path)
    parser.add_argument("--link-file",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    try:
        root=(Path(__file__).resolve().parent/"data").resolve()
        output=args.output.resolve()
        if not args.approve_dataset_combination or not output.is_relative_to(root) or output.exists():
            raise ValueError()
        audit=audit_file(args.profiles)
        corpus=json.loads(args.corpus_release.read_text(encoding="utf-8"))
        manifest=DatasetManifest(version="hackathon-release-v1",profile_file_sha256=audit.file_hash,
            profile_rows=tuple(p.row_hash for p in audit.accepted),corpus=tuple(corpus),
            review_reference=args.review_reference,combination_approved=True,
            payment_aggregates_approved=args.payment_file is not None,
            payment_file_sha256=hashlib.sha256(args.payment_file.read_bytes()).hexdigest() if args.payment_file else None,
            link_file_sha256=hashlib.sha256(args.link_file.read_bytes()).hexdigest() if args.link_file else None)
        output.parent.mkdir(parents=True,exist_ok=True)
        raw=manifest.model_dump_json().encode()
        with output.open("xb") as stream:
            stream.write(raw)
        print(json.dumps({"status":"LOCAL_MANIFEST_ONLY","eligible_profiles":len(audit.accepted),
            "rejected_rows":len(audit.rejected_lines),"manifest_sha256":hashlib.sha256(raw).hexdigest(),
            "external_requests":0}))
    except Exception:
        parser.exit(1,"RELEASE_MANIFEST_NOT_CREATED\n")

if __name__=="__main__":
    main()
