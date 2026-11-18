from dataclasses import dataclass

from app.schemas.document import DecisionType


@dataclass(frozen=True)
class SampleDocumentScenario:
    id: str
    title: str
    doc_type: str
    category: str
    expected_outcome: DecisionType
    description: str
    filename: str
    raw_text: str
    ocr_confidence: float
    applicant_name: str | None = None
    applicant_dob: str | None = None
    applicant_id_number: str | None = None


SAMPLE_SCENARIOS: dict[str, SampleDocumentScenario] = {
    "valid-passport": SampleDocumentScenario(
        id="valid-passport",
        title="Valid International Passport",
        doc_type="passport",
        category="identity",
        expected_outcome="PASS",
        description="Complete identity document with valid dates and exact applicant cross-check match.",
        filename="passport_aarav_mehta.txt",
        ocr_confidence=0.97,
        applicant_name="Aarav Mehta",
        applicant_dob="1994-06-18",
        applicant_id_number="Z8492014",
        raw_text="""REPUBLIC OF INDIA - PASSPORT
Type: P
Country: India
Passport No: Z8492014
Full Name: Aarav Mehta
Date of Birth: 1994-06-18
Date of Issue: 2022-04-12
Date of Expiry: 2032-04-11
Issuing Authority: Regional Passport Office Bengaluru
Address: 42 Indiranagar 100ft Road, Bengaluru 560038
""",
    ),
    "bank-statement-review": SampleDocumentScenario(
        id="bank-statement-review",
        title="Bank Statement (Name Discrepancy)",
        doc_type="bank_statement",
        category="financial",
        expected_outcome="MANUAL_REVIEW",
        description="Financial statement with minor applicant name spelling difference, routed to Manual Review.",
        filename="bank_statement_priya_sharma.txt",
        ocr_confidence=0.91,
        applicant_name="Priya Kumari Sharma",
        applicant_dob=None,
        applicant_id_number=None,
        raw_text="""MONTHLY BANK STATEMENT
Bank Name: Horizon National Bank
Account Holder: Priya Sharma
Account Number: ****-****-7821
Statement Period: 2026-09-01 to 2026-09-30
Issue Date: 2026-10-02
Currency: USD
Closing Balance: $18,450.75
Address: 210 Market Street, Suite 400, San Francisco, CA
""",
    ),
    "expired-license-fail": SampleDocumentScenario(
        id="expired-license-fail",
        title="Expired Driver's License + DOB Conflict",
        doc_type="drivers_license",
        category="identity",
        expected_outcome="FAIL",
        description="Expired identity document whose extracted DOB conflicts with applicant record.",
        filename="drivers_license_rohan_verma.txt",
        ocr_confidence=0.94,
        applicant_name="Rohan Verma",
        applicant_dob="1992-03-14",
        applicant_id_number="DL-04-2016009821",
        raw_text="""DEPARTMENT OF MOTOR VEHICLES - DRIVER LICENSE
License Number: DL-04-2016009821
Full Name: Rohan Verma
Date of Birth: 1991-11-05
Date of Issue: 2018-05-10
Date of Expiry: 2023-05-10
Issuing Authority: State Transport Authority
Country: India
Address: 18 Sector 62, Noida, UP
""",
    ),
    "tax-form-pass": SampleDocumentScenario(
        id="tax-form-pass",
        title="Annual Tax Statement (W-2 / Income)",
        doc_type="tax_document",
        category="financial",
        expected_outcome="PASS",
        description="Verified annual financial tax record with employer, tax ID, and reported income.",
        filename="tax_statement_ananya_kapoor.txt",
        ocr_confidence=0.96,
        applicant_name="Ananya Kapoor",
        applicant_dob=None,
        applicant_id_number="TIN-98421-IN",
        raw_text="""FORM W-2 WAGE AND TAX STATEMENT
Taxpayer Name: Ananya Kapoor
Tax ID: TIN-98421-IN
Employer Name: Meridian FinTech Systems Inc.
Statement Period: Tax Year 2025
Issue Date: 2026-01-28
Currency: USD
Total Wages: $124,800.00
Address: 745 Pine Avenue, Austin, TX 78701
""",
    ),
}
