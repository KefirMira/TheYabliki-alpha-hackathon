"""Only invented data. No real dataset or keys."""
import json
from services.dataset_analysis import DatasetManifest, sha, canonical
from company_import.validation import HEADERS, FLAGS, ENUMS, SOURCE

def attributes(source="SYNTH-COMPANY-A"):
    row = {key:"synthetic" for key in HEADERS}
    for key in FLAGS:
        row[key]="0"
    for key, values in ENUMS.items():
        row[key]=next(iter(sorted(v for v in values if v)))
    row.update(SYNTHETIC_U=source,MAINOKVED_CODE="28.99",MAINOKVED_NAME="Учебное производство оборудования",
        REVENUE_COMPANY="123.45",REGION="Учебный регион",CL_PRODUCT_LOA_MARK="1")
    return row

def manifest(attrs=None):
    attrs = attrs or attributes()
    fragment = "Учебная ключевая ставка и кредитование: условия договора неизвестны. Ставка не доказывает стоимость кредита."
    return DatasetManifest(version="hackathon-release-v1",profile_file_sha256="a"*64,
        profile_rows=(sha(canonical(attrs)),),corpus=(
            dict(source="synthetic-rate.txt",page=1,chunk_id=1,text=fragment,
                 text_sha256=sha(fragment),publisher="SYNTHETIC",format="TXT",date=None),),
        review_reference="synthetic-review-only",combination_approved=True)

async def seed_dataset(c,news,attrs=None):
    attrs=attrs or attributes()
    origin={"_company_profile_csv_v1":{"source":SOURCE,"current":{
        "file_sha256":"a"*64,"attributes":attrs}}}
    await c.execute("UPDATE companies SET source_data=$1::jsonb WHERE source_id=$2",
        json.dumps(origin,ensure_ascii=False),attrs["SYNTHETIC_U"])
    await c.execute("UPDATE news_articles SET content='Учебная ключевая ставка и кредитование' WHERE id=$1",news)
