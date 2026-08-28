from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime, timezone

OUT=Path(__file__).resolve().parent.parent/"reports"; OUT.mkdir(exist_ok=True)

def build_pdf(dataset_id, p, ins):
    path=OUT/f"{dataset_id}.pdf"; styles=getSampleStyleSheet(); doc=SimpleDocTemplate(str(path),pagesize=A4)
    story=[Paragraph("AI Data Analytics Report",styles["Title"]),Paragraph(datetime.now(timezone.utc).strftime("Analysis time: %Y-%m-%d %H:%M UTC"),styles["Normal"]),Spacer(1,12)]
    story += [Paragraph("Dataset Overview",styles["Heading2"]), Paragraph(f"Rows: {p['rows']} | Columns: {p['columns']} | Quality score: {p['data_quality_score']}",styles["Normal"]),Spacer(1,8)]
    story += [Paragraph("Key KPIs",styles["Heading2"])]
    data=[["Metric","Value"]]+[[x["label"],str(x["value"])] for x in ins.get("kpis",[])[:12]]
    story += [Table(data,style=TableStyle([('BACKGROUND',(0,0),(-1,0),colors.lightgrey),('GRID',(0,0),(-1,-1),0.25,colors.grey)])),Spacer(1,10)]
    for title,key in [("Trends","trends"),("Anomalies","anomalies"),("Correlations","correlations"),("Recommendations","recommendations")]:
        story.append(Paragraph(title,styles["Heading2"]))
        vals=ins.get(key,[]); story.append(Paragraph("<br/>".join([str(v) for v in vals]) if vals else "No material findings.",styles["BodyText"]))
        story.append(Spacer(1,8))
    doc.build(story); return path
