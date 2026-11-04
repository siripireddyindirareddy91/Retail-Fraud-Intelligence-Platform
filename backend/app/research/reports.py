import io
import json
from xml.sax.saxutils import escape


def report_pdf(run, dataset_name=""):
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    result, config = run["result"], run["config"]
    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=(595.28, 841.89), leftMargin=43, rightMargin=43, topMargin=45, bottomMargin=43)
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#164f3b")
    story = [Paragraph("Retail Fraud Intelligence", styles["Title"]), Paragraph("Reproducible research evaluation report", styles["Heading2"]), Spacer(1, 14)]
    for title, value in [("Run", run["id"]), ("Analysis", run["kind"]), ("Dataset", dataset_name or str(config.get("dataset_id", "Not applicable"))), ("Created (UTC)", str(run["created_at"]))]:
        story.append(Paragraph(f"<b>{escape(title)}:</b> {escape(value)}", styles["BodyText"]))
    story.extend([Spacer(1, 14), Paragraph("Configuration", styles["Heading2"])])
    for key, value in config.items():
        story.append(Paragraph(f"<b>{escape(str(key))}:</b> {escape(str(value))}", styles["BodyText"]))
    metrics = result.get("metrics", {})
    summary = result.get("summary", [])
    if metrics:
        story.extend([Spacer(1, 12), Paragraph("Held-out model performance", styles["Heading2"])])
        rows = [["Metric", "Value"]] + [[name, "Undefined" if metrics.get(name) is None else f"{metrics[name]:.4f}"] for name in ["precision", "recall", "f1", "pr_auc", "roc_auc", "fpr", "fnr", "brier", "ece"]]
        table = Table(rows, colWidths=[260, 220])
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#164f3b")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f0f6f2"), colors.white]), ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8)]))
        story.append(table)
    if summary or metrics:
        fig, ax = plt.subplots(figsize=(7, 3.2), layout="constrained")
        if summary:
            x = list(range(len(summary)))
            ax.bar([i - .18 for i in x], [item["baseline_recall"] for item in summary], width=.36, color="#227b5f", label="Baseline")
            ax.bar([i + .18 for i in x], [item["augmented_recall"] for item in summary], width=.36, color="#d59d53", label="Augmented")
            ax.set_xticks(x, [item["condition"] for item in summary])
            ax.set_ylabel("Recall")
            ax.legend(frameon=False)
        else:
            keys = ["precision", "recall", "f1", "pr_auc", "roc_auc"]
            valid = [key for key in keys if metrics.get(key) is not None]
            ax.bar(valid, [metrics[key] for key in valid], color="#227b5f")
        ax.set_ylim(0, 1.05)
        ax.spines[["top", "right"]].set_visible(False)
        image = io.BytesIO()
        fig.savefig(image, format="png", dpi=150)
        plt.close(fig)
        image.seek(0)
        story.extend([Spacer(1, 14), Image(image, width=490, height=224)])
    story.extend([Spacer(1, 16), Paragraph("Findings and limitations", styles["Heading2"]), Paragraph(escape(str(result.get("limitations", result.get("limitation", "Results describe an artificial population. Distribution similarity is not a privacy guarantee; model explanations are not proof of actual fraud.")))), styles["BodyText"]), Paragraph("Synthetic augmentation is not assumed to improve detection. PR-AUC means average precision. Undefined metrics remain undefined. Review test hashes, thresholds and configurations before comparing runs.", styles["BodyText"])])
    # Keep full results accessible, with bounded line lengths that wrap safely.
    story.extend([PageBreak(), Paragraph("Result details", styles["Heading2"])])
    text = json.dumps(result, indent=2, sort_keys=True, default=str)
    if len(text) > 24000:
        text = text[:24000] + "\n[Details abbreviated for PDF; full results are available through the JSON artifact/API.]"
    for line in text.splitlines():
        for start in range(0, max(1, len(line)), 90):
            story.append(Paragraph(escape(line[start:start + 90]) or " ", styles["Code"]))
    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#61786c"))
        canvas.drawString(43, 24, "Fictional data research | Retail Fraud Intelligence Platform")
        canvas.drawRightString(552, 24, f"Page {doc.page}")
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
