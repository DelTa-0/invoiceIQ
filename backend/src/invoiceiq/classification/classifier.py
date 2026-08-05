from __future__ import annotations

import re

from .models import Classification, DocType

_KEYWORD_SETS: dict[DocType, tuple[str, ...]] = {
    DocType.INVOICE: (
        "rechnung", "invoice", "faktura", "facture", "fattura",
        "factuur", "fatura", "rechnungsnummer", "invoice number",
        "invoice date", "rechnungsdatum", "zahlungsziel",
        "payment terms", "due date", "fällig am",
    ),
    DocType.RECEIPT: (
        "receipt", "quittung", "kassenbeleg", "bon", "till receipt",
        "point of sale", "pos", "cashier", "belegnummer",
        "zahlungsbeleg", "payment receipt",
    ),
    DocType.PURCHASE_ORDER: (
        "purchase order", "bestellung", "bestellnummer", "po number",
        "purchase order number", "bestelldatum", "order date",
        "Lieferant", "vendor", "buyer", "besteller",
    ),
    DocType.PROFORMA: (
        "proforma", "pro-forma", "pro forma", "vorabrechnung",
        "provisional invoice", "angebot", "angebotsnummer",
        "offer", "quotation", "angebotstyp",
    ),
    DocType.CREDIT_NOTE: (
        "credit note", "gutschrift", "creditmemo", "credit memo",
        "storno", "rückerstattung", "refund", "gutschriftenummer",
        "credit number", "gutscher",
    ),
    DocType.CONTRACT: (
        "contract", "vertrag", "vereinbarung", "agreement",
        "dienstleistungsvertrag", "werkvertrag", "kaufvertrag",
        "mietvertrag", "lease", "partnerschaft", "partnership",
        "bedingungen", "conditions", "clause", "klausel",
        "unterschrift", "signature", "unterzeichnet",
    ),
    DocType.SHIPPING_DOCUMENT: (
        "shipping", "lieferschein", "delivery note", "packlist",
        "packing list", "frachtbrief", "waybill", "consignment",
        "tracking", "versand", "shipment", "logistics",
        "carrier", "spedition", "transport", "container",
    ),
    DocType.CUSTOMS_FORM: (
        "customs", "zoll", "declaration", "zollerklärung",
        "customs declaration", "cn22", "cn23", "formular",
        "export", "import", "zollamt", " customs ",
        "declaration number", "zollnummer",
    ),
    DocType.BANK_STATEMENT: (
        "bank statement", "kontoauszug", "kontoumsatz", "kontobewegung",
        "bankauszug", "girokonto", "kontoauszug", "umsatz",
        "saldo", "buchung", "transaction", "transaktion",
        "kontonummer", "bankleitzahl", "blz",
    ),
    DocType.TAX_DOCUMENT: (
        "tax", "steuer", "steuererklärung", "tax return",
        "steuerbescheid", "steueridentifikationsnummer",
        "tax id", "tin", "steuerpflicht", "vat return",
        "gewinnermittlung", "jahresabschluss",
    ),
    DocType.EMPLOYEE_DOCUMENT: (
        "employee", "mitarbeiter", "angestellte", "lohn", "gehalt",
        "payroll", "personalausweis", "arbeitsvertrag",
        "beschäftigung", "employment", "jahreslohn",
    ),
    DocType.INSURANCE_CLAIM: (
        "insurance", "versicherung", "schadenmeldung", "claim",
        "versicherungsschein", "police", "deckung",
        "versicherungnehmer", "versicherunggeber",
    ),
    DocType.LAND_REGISTRY: (
        "grundbuch", "land register", "grundbucheintrag",
        "grunddaten", "liegenschaft", "immobilie", "property register",
    ),
    DocType.COURT_ORDER: (
        "gericht", "court", "beschluss", "urteil", "verfügung",
        "gerichtsbeschluss", "lawsuit", "prozess", "klage",
    ),
    DocType.FINANCIAL_REPORT: (
        "financial report", "finanzbericht", "jahresbericht",
        "geschäftsbericht", "financial statement", "report",
        "bericht", "analyse", "analysebericht",
    ),
    DocType.BALANCE_SHEET: (
        "balance sheet", "bilanz", "vermögensübersicht",
        "aktiva", "passiva", "bilanzkonto", "bilanzstamm",
    ),
    DocType.INCOME_STATEMENT: (
        "income statement", "gewinn- und verlustrechnung",
        "guv", "erfolgsrechnung", "gewinn", "verlust",
        "ertrag", "aufwand", "gewinnmarge",
    ),
}


class DocumentClassifier:
    """Keyword-driven document type classifier.

    Scans OCR text for document-type keywords and returns the
    best match with a confidence score.  Designed to be replaced
    by an ML model later without changing the surrounding pipeline.
    """

    def __init__(self, keyword_sets: dict[DocType, tuple[str, ...]] | None = None) -> None:
        self._keyword_sets = keyword_sets or _KEYWORD_SETS
        self._compiled: dict[DocType, list[re.Pattern[str]]] = {
            dt: [re.compile(re.escape(kw), re.IGNORECASE) for kw in kws]
            for dt, kws in self._keyword_sets.items()
        }

    def classify(self, text: str) -> Classification:
        scores: dict[DocType, list[str]] = {}
        for dt, patterns in self._compiled.items():
            matched = [p.pattern for p in patterns if p.search(text)]
            if matched:
                scores[dt] = matched

        if not scores:
            return Classification(doc_type=DocType.UNKNOWN, confidence=0.0)

        best_dt = max(scores, key=lambda dt: len(scores[dt]))
        count = len(scores[best_dt])
        total = sum(len(v) for v in scores.values())
        confidence = round(count / max(total, 1), 4)

        return Classification(
            doc_type=best_dt,
            confidence=confidence,
            keywords_matched=tuple(scores[best_dt]),
        )


def classify_document(text: str) -> tuple[DocType, float]:
    """Convenience wrapper returning (doc_type, confidence)."""
    result = DocumentClassifier().classify(text)
    return result.doc_type, result.confidence