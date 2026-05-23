"""
PAKIES PQC AUDIT REPORT v2 — Lesbare Version (Hell auf Dunkel)
pip install reportlab kyber-py dilithium-py
"""
import os, time, base64, hashlib
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, Flowable
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from kyber_py.ml_kem import ML_KEM_768
from dilithium_py.ml_dsa import ML_DSA_65

# ─── FARBEN — DUNKEL AUF DUNKEL, LESBAR ──────────────────────────────────────
GOLD    = HexColor("#C9A84C")
BLACK   = HexColor("#0A0A0A")
BG      = HexColor("#111111")   # Seiten-Hintergrund
CARD    = HexColor("#1A1A1A")   # Karten-Hintergrund
CARD2   = HexColor("#222222")   # Alternierende Zeilen
BORDER  = HexColor("#333333")   # Tabellenrahmen
TEXT    = HexColor("#E8E8E0")   # Haupttext — warm-weiß, gut lesbar
MUTED   = HexColor("#AAAAAA")   # Sekundärtext
DIM     = HexColor("#666666")   # Dezenter Text
RED     = HexColor("#E05252")   # Kritisch
ORANGE  = HexColor("#E8943A")   # Warnung
GREEN   = HexColor("#4CAF7D")   # OK
W, H    = A4

# ─── HINTERGRUND-CANVAS ───────────────────────────────────────────────────────
class HeaderCanvas:
    def __init__(self, company, date_str):
        self.company = company
        self.date_str = date_str

    def __call__(self, canvas, doc):
        canvas.saveState()
        # Ganzseitiger dunkler Hintergrund
        canvas.setFillColor(BG)
        canvas.rect(0, 0, W, H, fill=1, stroke=0)
        # Header-Balken
        canvas.setFillColor(BLACK)
        canvas.rect(0, H - 22*mm, W, 22*mm, fill=1, stroke=0)
        # Goldene Linie unter Header
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(1)
        canvas.line(0, H - 22*mm, W, H - 22*mm)
        # MP Monogram
        canvas.setFillColor(GOLD)
        canvas.setFont("Helvetica-Bold", 16)
        canvas.drawString(20*mm, H - 14*mm, "MP")
        # Header Text
        canvas.setFillColor(TEXT)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(35*mm, H - 11*mm, "PAKIES MANAGEMENT & BUSINESS CONSULTING")
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(35*mm, H - 16*mm, "POST-QUANTUM CRYPTOGRAPHY AUDIT REPORT")
        # Firma rechts
        canvas.setFillColor(GOLD)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawRightString(W - 20*mm, H - 11*mm, self.company.upper())
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(W - 20*mm, H - 16*mm, self.date_str)
        # Footer
        canvas.setFillColor(BLACK)
        canvas.rect(0, 0, W, 12*mm, fill=1, stroke=0)
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(0.5)
        canvas.line(0, 12*mm, W, 12*mm)
        canvas.setFillColor(DIM)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(20*mm, 4*mm, "VERTRAULICH — Nur fuer den internen Gebrauch des Auftraggebers")
        canvas.setFillColor(GOLD)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.drawRightString(W - 20*mm, 4*mm, f"Seite {doc.page}")
        canvas.restoreState()

# ─── CUSTOM FLOWABLES ─────────────────────────────────────────────────────────
class GoldLine(Flowable):
    def __init__(self, width=None, thickness=1):
        Flowable.__init__(self)
        self.line_width = width or (W - 40*mm)
        self.thickness = thickness
    def draw(self):
        self.canv.setStrokeColor(GOLD)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 0, self.line_width, 0)

class RiskBadge(Flowable):
    def __init__(self, label, color, score, max_score):
        Flowable.__init__(self)
        self.label = label; self.color = color
        self.score = score; self.max_score = max_score
        self.width = W - 40*mm; self.height = 30*mm
    def draw(self):
        c = self.canv
        # Hintergrund
        c.setFillColor(CARD)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        # Farbiger linker Balken
        c.setFillColor(self.color)
        c.rect(0, 0, 4, self.height, fill=1, stroke=0)
        # Label
        c.setFillColor(self.color)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(8*mm, 19*mm, self.label)
        # Score
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8)
        c.drawRightString(self.width - 6*mm, 19*mm, f"{self.score}/{self.max_score} Punkte")
        # Progress bar background
        bx, by, bw, bh = 8*mm, 10*mm, self.width - 16*mm, 5*mm
        c.setFillColor(BORDER)
        c.roundRect(bx, by, bw, bh, 2, fill=1, stroke=0)
        # Progress bar fill
        c.setFillColor(self.color)
        fill = bw * (self.score / self.max_score)
        c.roundRect(bx, by, fill, bh, 2, fill=1, stroke=0)

# ─── STYLES ───────────────────────────────────────────────────────────────────
def make_styles():
    return {
        "h1":    ParagraphStyle("h1",    fontName="Helvetica-Bold", fontSize=28, textColor=TEXT,  spaceAfter=2*mm, spaceBefore=4*mm, leading=32),
        "h2":    ParagraphStyle("h2",    fontName="Helvetica-Bold", fontSize=13, textColor=GOLD,  spaceAfter=3*mm, spaceBefore=6*mm, leading=16),
        "h3":    ParagraphStyle("h3",    fontName="Helvetica-Bold", fontSize=10, textColor=TEXT,  spaceAfter=2*mm, spaceBefore=4*mm),
        "body":  ParagraphStyle("body",  fontName="Helvetica",      fontSize=9,  textColor=TEXT,  spaceAfter=2*mm, leading=14),
        "small": ParagraphStyle("small", fontName="Helvetica",      fontSize=8,  textColor=MUTED, spaceAfter=1*mm, leading=12),
        "label": ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=7,  textColor=GOLD,  spaceAfter=2*mm, charSpace=2),
        "mono":  ParagraphStyle("mono",  fontName="Courier",        fontSize=8,  textColor=GOLD,  spaceAfter=1*mm, leading=12),
        "dim":   ParagraphStyle("dim",   fontName="Helvetica",      fontSize=8,  textColor=DIM,   spaceAfter=1*mm),
    }

# ─── AUDIT LOGIK ──────────────────────────────────────────────────────────────
def run_pqc_audit(client_data):
    findings = []; score = 0; max_score = 0
    checks = [
        {"category": "TRANSPORT SECURITY", "question": "TLS-Version",
         "value": client_data.get("tls_version", "Unbekannt"), "max": 3,
         "scoring": {"TLS 1.3": (3, GREEN, "Aktuell — PQC-Erweiterung moeglich"), "TLS 1.2": (2, ORANGE, "Akzeptabel — Upgrade auf 1.3 empfohlen"), "TLS 1.1": (0, RED, "KRITISCH — Sofort-Upgrade erforderlich"), "Unbekannt": (1, ORANGE, "Inventur erforderlich")}},
        {"category": "ZERTIFIKATE", "question": "Zertifikats-Algorithmus",
         "value": client_data.get("cert_algorithm", "RSA 2048"), "max": 3,
         "scoring": {"RSA 4096": (2, ORANGE, "Uebergangsweise sicher — Migration planen"), "RSA 2048": (1, ORANGE, "PQC-Migration in 2–3 Jahren"), "ECC P-256": (2, ORANGE, "Von Shors Algorithmus gefaehrdet"), "PQC (ML-KEM)": (3, GREEN, "Zukunftssicher — NIST-konform"), "Unbekannt": (0, RED, "KRITISCH — Inventur sofort noetig")}},
        {"category": "GOVERNANCE", "question": "Kryptografie-Inventar",
         "value": client_data.get("crypto_inventory", "Nein"), "max": 3,
         "scoring": {"Vollstaendig": (3, GREEN, "Solide Basis fuer Migration"), "Teilweise": (1, ORANGE, "Inventar vervollstaendigen"), "Nein": (0, RED, "KRITISCH — Kein Ueberblick ueber Angriffsflaeche"), "In Planung": (1, ORANGE, "Priorisieren und umsetzen")}},
        {"category": "COMPLIANCE", "question": "Regulatorik",
         "value": client_data.get("regulatory", "Keine"), "max": 2,
         "scoring": {"DORA": (0, RED, "Pflicht bis 2025 — sofortiger Handlungsbedarf"), "NIS2": (0, RED, "Stand der Technik = PQC-Readiness"), "ISO 27001": (1, ORANGE, "Annex A.10 Kryptografie-Policy pruefen"), "Keine": (2, GREEN, "Kein unmittelbarer Compliance-Druck"), "Unbekannt": (0, RED, "Regulatorische Lage sofort klaeren")}},
        {"category": "DATENSCHUTZ", "question": "Datenhaltungsdauer",
         "value": client_data.get("data_lifetime", "Unbekannt"), "max": 3,
         "scoring": {"< 5 Jahre": (3, GREEN, "Geringes Harvest-Now-Decrypt-Later Risiko"), "5-10 Jahre": (1, ORANGE, "Mittleres Risiko — PQC-Migration priorisieren"), "< 10 Jahre": (0, RED, "KRITISCH — Daten heute bereits gefaehrdet"), "Dauerhaft": (0, RED, "Hoechste Prioritaet fuer PQC-Migration"), "Unbekannt": (0, RED, "Datenklassifizierung sofort durchfuehren")}},
        {"category": "STRATEGIE", "question": "PQC-Awareness Management",
         "value": client_data.get("pqc_awareness", "Nicht bekannt"), "max": 3,
         "scoring": {"Aktives Projekt": (3, GREEN, "Vorbildlich — technische Umsetzung beginnen"), "Bekannt, kein Budget": (1, ORANGE, "Business Case erstellen"), "Nicht bekannt": (0, RED, "Management-Briefing erforderlich"), "Kein CISO": (0, RED, "Sicherheitsverantwortung definieren")}},
    ]
    for c in checks:
        val = c["value"]
        pts, color, remark = c["scoring"].get(val, (1, ORANGE, "Nicht klassifizierbar"))
        score += pts; max_score += c["max"]
        findings.append({"category": c["category"], "question": c["question"], "value": val, "score": pts, "max": c["max"], "color": color, "remark": remark})
    pct = score / max_score
    if pct >= 0.7:   rl, rc, rd = "NIEDRIGES RISIKO", GREEN,  "Grundlegende Sicherheitshygiene vorhanden. Proaktive PQC-Planung empfohlen."
    elif pct >= 0.4: rl, rc, rd = "MITTLERES RISIKO", ORANGE, "Handlungsbedarf identifiziert. PQC-Roadmap innerhalb 12 Monaten empfehlenswert."
    else:            rl, rc, rd = "HOHES RISIKO",     RED,    "Kritische Luecken in der Kryptografie-Infrastruktur. Sofortiger Handlungsbedarf."
    return {"score": score, "max_score": max_score, "risk_label": rl, "risk_color": rc, "risk_desc": rd, "findings": findings}

def run_benchmark():
    t0 = time.perf_counter()
    ek, dk = ML_KEM_768.keygen(); sk, ct = ML_KEM_768.encaps(ek); rec = ML_KEM_768.decaps(dk, ct)
    kem = {"algo": "ML-KEM-768 (FIPS 203)", "time_ms": round((time.perf_counter()-t0)*1000,1), "ek_bytes": len(ek), "ct_bytes": len(ct), "valid": sk==rec}
    t0 = time.perf_counter()
    pk, sk2 = ML_DSA_65.keygen(); msg = b"PAKIES PQC Audit"; sig = ML_DSA_65.sign(sk2, msg); valid = ML_DSA_65.verify(pk, msg, sig)
    dsa = {"algo": "ML-DSA-65 (FIPS 204)", "time_ms": round((time.perf_counter()-t0)*1000,1), "pk_bytes": len(pk), "sig_bytes": len(sig), "valid": valid}
    return {"kem": kem, "dsa": dsa}

# ─── REPORT BUILDER ───────────────────────────────────────────────────────────
def build_report(client, output_path=None):
    date_str = datetime.now().strftime("%d.%m.%Y")
    company  = client.get("company", "Unternehmen")
    if not output_path:
        safe = company.replace(" ", "_").replace("/", "-")
        output_path = f"PAKIES_PQC_Audit_{safe}_{datetime.now().strftime('%Y%m%d')}.pdf"

    audit = run_pqc_audit(client)
    bench = run_benchmark()
    doc   = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=27*mm, bottomMargin=18*mm)
    hfn   = HeaderCanvas(company, date_str)
    S     = make_styles()
    story = []

    # ── SEITE 1: COVER ────────────────────────────────────────────────────────
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("POST-QUANTUM", S["label"]))
    story.append(Paragraph("CRYPTOGRAPHY<br/>AUDIT REPORT", S["h1"]))
    story.append(GoldLine(thickness=2))
    story.append(Spacer(1, 5*mm))

    # Info-Tabelle
    info = [
        ["AUFTRAGGEBER",   company],
        ["ANSPRECHPARTNER", client.get("contact",   "—")],
        ["BRANCHE",         client.get("industry",  "—")],
        ["MITARBEITER",     client.get("employees", "—")],
        ["DATUM",           date_str],
        ["BERICHTS-ID",     f"PAKIES-PQC-{datetime.now().strftime('%Y%m%d-%H%M')}"],
    ]
    it = Table(info, colWidths=[48*mm, 107*mm])
    it.setStyle(TableStyle([
        ("FONTNAME",      (0,0),(0,-1), "Helvetica-Bold"),
        ("FONTNAME",      (1,0),(1,-1), "Helvetica"),
        ("FONTSIZE",      (0,0),(-1,-1), 9),
        ("TEXTCOLOR",     (0,0),(0,-1),  GOLD),
        ("TEXTCOLOR",     (1,0),(1,-1),  TEXT),
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [CARD, CARD2]),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(-1,-1), 5),
        ("GRID",          (0,0),(-1,-1), 0.3, BORDER),
        ("LINEBEFORE",    (0,0),(0,-1),  2, GOLD),
    ]))
    story.append(it)
    story.append(Spacer(1, 6*mm))

    # Risk Badge
    story.append(Paragraph("GESAMTBEWERTUNG", S["label"]))
    story.append(RiskBadge(audit["risk_label"], audit["risk_color"], audit["score"], audit["max_score"]))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(audit["risk_desc"], S["body"]))
    story.append(Spacer(1, 6*mm))

    # Executive Summary
    story.append(Paragraph("EXECUTIVE SUMMARY", S["label"]))
    story.append(Paragraph(
        f"Dieser Report dokumentiert die PQC-Readiness von <b>{company}</b> auf Basis des "
        f"PAKIES Kryptografie-TUeV-Frameworks. Grundlage: FIPS 203 (ML-KEM), FIPS 204 (ML-DSA), "
        f"BSI TR-02102 und NIS2-Richtlinie. Der Bericht identifiziert konkrete Handlungsfelder "
        f"und liefert eine priorisierte Roadmap fuer die PQC-Migration.", S["body"]))
    story.append(PageBreak())

    # ── SEITE 2: FINDINGS ─────────────────────────────────────────────────────
    story.append(Paragraph("AUDIT-ERGEBNISSE", S["h2"]))
    story.append(GoldLine())
    story.append(Spacer(1, 3*mm))

    for f in audit["findings"]:
        pct = f["score"] / f["max"]
        bar = "█" * int(pct * 18) + "░" * (18 - int(pct * 18))
        color_hex = {GREEN: "#4CAF7D", ORANGE: "#E8943A", RED: "#E05252"}.get(f["color"], "#C9A84C")

        rows = [
            [Paragraph(f["category"], S["label"]),
             Paragraph(f'{f["score"]}/{f["max"]}', S["dim"])],
            [Paragraph(f["question"], S["body"]),
             Paragraph(f["remark"], S["small"])],
            [Paragraph(f'<font name="Courier" size="8" color="{color_hex}">{bar}</font>', S["mono"]),
             Paragraph(f["value"], S["small"])],
        ]
        t = Table(rows, colWidths=[95*mm, 60*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), CARD),
            ("LINEBEFORE",   (0,0),(0,-1),  3, f["color"]),
            ("LINEBELOW",    (0,-1),(-1,-1), 0.5, BORDER),
            ("TOPPADDING",   (0,0),(-1,-1), 3),
            ("BOTTOMPADDING",(0,0),(-1,-1), 3),
            ("LEFTPADDING",  (0,0),(-1,-1), 5),
            ("RIGHTPADDING", (0,0),(-1,-1), 5),
        ]))
        story.append(KeepTogether([t, Spacer(1, 3*mm)]))
    story.append(PageBreak())

    # ── SEITE 3: EMPFEHLUNGEN ─────────────────────────────────────────────────
    story.append(Paragraph("HANDLUNGSEMPFEHLUNGEN", S["h2"]))
    story.append(GoldLine())
    story.append(Spacer(1, 3*mm))

    for phase, color, actions in [
        ("SOFORT (0–4 Wochen)",        RED,    ["Kryptografie-Inventar aller Systeme erstellen", "Management-Briefing zu Quantum-Risiken durchfuehren", "Regulatorische Compliance-Gaps dokumentieren"]),
        ("KURZFRISTIG (1–3 Monate)",   ORANGE, ["TLS auf Version 1.3 aktualisieren", "PQC-Roadmap mit Zeithorizont erstellen", "Hybrid-Kryptografie fuer kritische Systeme planen"]),
        ("MITTELFRISTIG (3–12 Monate)",GOLD,   ["Pilot: Ein System auf ML-KEM-768 migrieren", "Zertifikate schrittweise auf PQC umstellen", "NIS2-konformes Kryptografie-Dokument erstellen"]),
    ]:
        color_hex = {RED: "#E05252", ORANGE: "#E8943A", GOLD: "#C9A84C"}[color]
        header_row = [[Paragraph(f'<font color="{color_hex}">{phase}</font>', S["h3"])]]
        ht = Table(header_row, colWidths=[155*mm])
        ht.setStyle(TableStyle([
            ("BACKGROUND",  (0,0),(-1,-1), CARD2),
            ("LINEBEFORE",  (0,0),(0,-1),  3, color),
            ("TOPPADDING",  (0,0),(-1,-1), 5),
            ("BOTTOMPADDING",(0,0),(-1,-1),5),
            ("LEFTPADDING", (0,0),(-1,-1), 6),
        ]))
        story.append(ht)
        for a in actions:
            row = [[Paragraph(f'<font color="{color_hex}">  ▶</font>  {a}', S["body"])]]
            at = Table(row, colWidths=[155*mm])
            at.setStyle(TableStyle([
                ("BACKGROUND",   (0,0),(-1,-1), CARD),
                ("LINEBEFORE",   (0,0),(0,-1),  3, color),
                ("TOPPADDING",   (0,0),(-1,-1), 3),
                ("BOTTOMPADDING",(0,0),(-1,-1), 3),
                ("LEFTPADDING",  (0,0),(-1,-1), 6),
            ]))
            story.append(at)
        story.append(Spacer(1, 5*mm))
    story.append(PageBreak())

    # ── SEITE 4: BENCHMARK + ROADMAP ─────────────────────────────────────────
    story.append(Paragraph("TECHNISCHER NACHWEIS", S["h2"]))
    story.append(GoldLine())
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("Live-Benchmark — ausgefuehrt waehrend der Report-Generierung:", S["body"]))
    story.append(Spacer(1, 4*mm))

    for label, b in [("ML-KEM-768 (FIPS 203) — Schluessel-Encapsulation", bench["kem"]),
                     ("ML-DSA-65  (FIPS 204) — Digitale Signaturen",       bench["dsa"])]:
        story.append(Paragraph(label, S["h3"]))
        if "ek_bytes" in b:
            rows = [["PARAMETER","WERT","STATUS"],
                    ["Algorithmus", b["algo"], "NIST-Standard"],
                    ["Ausfuehrungszeit", f"{b['time_ms']} ms", "Produktionstauglich"],
                    ["Encapsulation Key", f"{b['ek_bytes']} Bytes", "Oeffentlich"],
                    ["Ciphertext", f"{b['ct_bytes']} Bytes", "Uebertragungsgroesse"],
                    ["Validierung", "ERFOLGREICH" if b["valid"] else "FEHLER", "Integritaet OK"]]
        else:
            rows = [["PARAMETER","WERT","STATUS"],
                    ["Algorithmus", b["algo"], "NIST-Standard"],
                    ["Ausfuehrungszeit", f"{b['time_ms']} ms", "Produktionstauglich"],
                    ["Public Key", f"{b['pk_bytes']} Bytes", "Verteilbar"],
                    ["Signaturgroesse", f"{b['sig_bytes']} Bytes", "Dokumentenintegritaet"],
                    ["Validierung", "ERFOLGREICH" if b["valid"] else "FEHLER", "Integritaet OK"]]
        bt = Table(rows, colWidths=[50*mm, 65*mm, 50*mm])
        bt.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,0),  CARD2),
            ("ROWBACKGROUNDS",(0,1),(-1,-1), [CARD, HexColor("#161616")]),
            ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
            ("FONTNAME",      (0,1),(-1,-1), "Helvetica"),
            ("FONTSIZE",      (0,0),(-1,-1), 8),
            ("TEXTCOLOR",     (0,0),(-1,0),  GOLD),
            ("TEXTCOLOR",     (0,1),(-1,-1), TEXT),
            ("TEXTCOLOR",     (1,-1),(1,-1), GREEN if b["valid"] else RED),
            ("TOPPADDING",    (0,0),(-1,-1), 3),
            ("BOTTOMPADDING", (0,0),(-1,-1), 3),
            ("LEFTPADDING",   (0,0),(-1,-1), 5),
            ("GRID",          (0,0),(-1,-1), 0.3, BORDER),
            ("LINEBEFORE",    (0,0),(0,-1),  2, GOLD),
        ]))
        story.append(bt)
        story.append(Spacer(1, 5*mm))

    story.append(Paragraph("MIGRATIONS-ROADMAP", S["h2"]))
    story.append(GoldLine())
    story.append(Spacer(1, 3*mm))
    rm = [
        ["PHASE",             "ZEITRAUM",   "MASSNAHME",                          "AUFWAND"],
        ["1 — Inventur",      "Woche 1–2",  "Kryptografie-Inventar erstellen",    "1–2 Tage"],
        ["2 — Pilot",         "Monat 1",    "Ein System auf ML-KEM migrieren",    "3–5 Tage"],
        ["3 — Hybrid",        "Monat 2–3",  "PQC parallel zu RSA betreiben",      "1–2 Wochen"],
        ["4 — Migration",     "Monat 3–6",  "RSA schrittweise abloesen",          "4–8 Wochen"],
        ["5 — Zertifizierung","Monat 6",    "NIS2-konformes Dokument erstellen",  "1 Woche"],
    ]
    rmt = Table(rm, colWidths=[38*mm, 28*mm, 72*mm, 27*mm])
    rmt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  CARD2),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [CARD, HexColor("#161616")]),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTNAME",      (0,1),(-1,-1), "Helvetica"),
        ("FONTSIZE",      (0,0),(-1,-1), 8),
        ("TEXTCOLOR",     (0,0),(-1,0),  GOLD),
        ("TEXTCOLOR",     (0,1),(-1,-1), TEXT),
        ("TEXTCOLOR",     (0,1),(0,-1),  GOLD),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(-1,-1), 5),
        ("GRID",          (0,0),(-1,-1), 0.3, BORDER),
        ("LINEBEFORE",    (0,0),(0,-1),  2, GOLD),
    ]))
    story.append(rmt)
    story.append(Spacer(1, 6*mm))

    # CTA
    cta = Table([[
        Paragraph("NAECHSTER SCHRITT", S["label"]),
        Paragraph("Kostenloser 30-Min-Call: Top-3-Prioritaeten besprechen und individuelles Angebot erstellen.", S["small"]),
        Paragraph("linkedin.com/in/marcelpakies", S["mono"]),
    ]], colWidths=[155*mm])
    cta.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), CARD),
        ("LINEBEFORE",   (0,0),(0,-1),  3, GOLD),
        ("LINEABOVE",    (0,0),(-1,0),  1, GOLD),
        ("LINEBELOW",    (0,-1),(-1,-1),1, GOLD),
        ("TOPPADDING",   (0,0),(-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("LEFTPADDING",  (0,0),(-1,-1), 7),
    ]))
    story.append(cta)

    doc.build(story, onFirstPage=hfn, onLaterPages=hfn)
    print(f"Report erstellt: {output_path}")
    return output_path

# ─── AUSFÜHREN ────────────────────────────────────────────────────────────────
demo_client = {
    "company":          "Muster Maschinenbau GmbH",
    "contact":          "Thomas Weber (IT-Leiter)",
    "industry":         "Maschinenbau",
    "employees":        "320",
    "tls_version":      "TLS 1.2",
    "cert_algorithm":   "RSA 2048",
    "crypto_inventory": "Teilweise",
    "regulatory":       "ISO 27001",
    "data_lifetime":    "5-10 Jahre",
    "pqc_awareness":    "Bekannt, kein Budget",
}

path = build_report(demo_client)
