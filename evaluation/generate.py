"""Generate benchmark candidates strictly from extracted evidence."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from evaluation.extract import evidence_from_ids, excerpt_index
from evaluation.paths import TARGET_QUOTAS
from evaluation.schema import normalize_question

LANG_LABEL = {"en": "English", "hi": "Hindi", "kn": "Kannada"}


def _find(
    excerpts: Iterable[Dict[str, Any]],
    scheme_id: str,
    contains: Optional[str] = None,
    field: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    for item in excerpts:
        if item.get("scheme_id") != scheme_id:
            continue
        if field and item.get("field") != field:
            continue
        if contains and contains.lower() not in item.get("excerpt", "").lower():
            continue
        return item
    return None


def _ids(*items: Optional[Dict[str, Any]]) -> List[str]:
    return [item["id"] for item in items if item]


def _phrases(*texts: str) -> List[str]:
    out: List[str] = []
    for text in texts:
        cleaned = re.sub(r"\s+", " ", text).strip()
        if len(cleaned) >= 4:
            out.append(cleaned)
    return out


def _case(
    *,
    cid: str,
    scheme: str,
    category: str,
    difficulty: str,
    language: str,
    question: str,
    expected_behavior: str,
    excerpts_by_id: Dict[str, Dict[str, Any]],
    evidence_ids: List[str],
    ground_truth: Dict[str, Any],
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = {
        "id": cid,
        "scheme": scheme,
        "category": category,
        "difficulty": difficulty,
        "language": language,
        "question": question,
        "expected_behavior": expected_behavior,
        "ground_truth": ground_truth,
        "evidence": evidence_from_ids(excerpts_by_id, evidence_ids),
    }
    if extra:
        payload.update(extra)
    return payload


def _factual_from_excerpt(
    cid: str,
    scheme: str,
    difficulty: str,
    question: str,
    item: Dict[str, Any],
    excerpts_by_id: Dict[str, Dict[str, Any]],
    extra_phrases: Optional[List[str]] = None,
) -> Dict[str, Any]:
    phrases = extra_phrases or _phrases(*item["excerpt"].split()[:12])
    # Prefer distinctive tokens from the excerpt rather than the first 12 words.
    distinctive = [
        token
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9'/%-]{3,}", item["excerpt"])
        if token.lower() not in {"this", "that", "with", "from", "under", "scheme", "must"}
    ][:6]
    keyphrases = extra_phrases or (distinctive if distinctive else _phrases(item["excerpt"][:80]))
    return _case(
        cid=cid,
        scheme=scheme,
        category="factual",
        difficulty=difficulty,
        language="en",
        question=question,
        expected_behavior="answer_from_evidence",
        excerpts_by_id=excerpts_by_id,
        evidence_ids=[item["id"]],
        ground_truth={
            "facts": [item["excerpt"]],
            "required_keyphrases": keyphrases,
            "eligibility_status": None,
        },
    )


def generate_factual(excerpts: List[Dict[str, Any]], excerpts_by_id: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    specs: List[tuple] = [
        ("pmfby", "Pradhan Mantri Fasal Bima", "What is the official name of the central crop insurance scheme described as PMFBY?", "easy", ["Pradhan Mantri Fasal Bima Yojana", "PMFBY"]),
        ("pmfby", "Ministry of Agriculture", "Which ministry administers PMFBY according to the scheme note?", "easy", ["Ministry of Agriculture", "Farmers Welfare"]),
        ("pmfby", "pmfby.gov.in", "Which official PMFBY portal is listed in the scheme note?", "easy", ["pmfby.gov.in"]),
        ("pmfby", "yield losses", "What kind of farmer losses does PMFBY insure against?", "easy", ["yield losses", "crop insurance"]),
        ("pmfby", "drought, flood, pest", "Which natural risks does the PMFBY note mention as examples?", "easy", ["drought", "flood", "pest"]),
        ("pmfby", "notified crops in notified areas", "Who can enroll in PMFBY according to the public scheme description?", "medium", ["notified crops", "notified areas"]),
        ("pmfby", "loanee and", "Does PMFBY enrollment include loanee and non-loanee farmers?", "medium", ["loanee", "non-loanee"]),
        ("pmfby", "Common Service Centres", "Through which channels can farmers typically enroll in PMFBY?", "medium", ["banks", "Common Service Centres", "PMFBY portal"]),
        ("pmfby", "Financial compensation", "What benefit does PMFBY provide when yield loss is assessed?", "easy", ["Financial compensation", "yield loss"]),
        ("pmfby", "Premium rates", "How are PMFBY farmer premiums described in the scheme note?", "medium", ["subsidized", "Central", "State"]),
        ("pmfby", "season-specific", "Are PMFBY sum insured, premium, and cut-off dates fixed in the seed note?", "hard", ["season-specific"]),
        ("pmfby", "Land records", "What land-related document is commonly required at PMFBY enrollment?", "easy", ["Land records"]),
        ("pmfby", "Bank account details and Aadhaar", "Which identity and payment details are commonly required for PMFBY enrollment?", "easy", ["Bank account", "Aadhaar"]),
        ("pmfby", "Crop and survey", "What location details are commonly required for PMFBY enrollment?", "easy", ["Crop", "village"]),
        ("shakti", "Shakti Scheme", "What is the name of the Karnataka free bus travel scheme for women?", "easy", ["Shakti"]),
        ("shakti", "Transport Department", "Which Karnataka department is listed for the Shakti scheme?", "easy", ["Transport Department"]),
        ("shakti", "free travel for eligible women", "What is the purpose of the Shakti scheme?", "easy", ["free travel", "women"]),
        ("shakti", "Women citizens of Karnataka", "Who are the intended Shakti free-travel beneficiaries?", "easy", ["Women", "Karnataka"]),
        ("shakti", "KSRTC", "On which state transport services does Shakti apply according to the note?", "medium", ["KSRTC"]),
        ("shakti", "Men are not eligible", "Are men eligible for free travel under Shakti?", "easy", ["Men are not eligible"]),
        ("shakti", "Zero fare", "What fare do eligible women pay on notified Shakti bus services?", "easy", ["Zero fare"]),
        ("shakti", "No separate online application", "Is a separate online application required merely to board under Shakti?", "medium", ["No separate online application"]),
        ("shakti", "photo identity", "What document may a conductor request under Shakti?", "easy", ["photo identity"]),
        ("shakti", "sevasindhu.karnataka.gov.in", "Which Karnataka citizen portal is listed for Shakti grievances or clarifications?", "easy", ["sevasindhu.karnataka.gov.in"]),
        ("anna-bhagya", "Anna Bhagya", "What is the name of the Karnataka food security scheme in the seed note?", "easy", ["Anna Bhagya"]),
        ("anna-bhagya", "Food, Civil Supplies", "Which Karnataka department administers Anna Bhagya according to the note?", "easy", ["Food, Civil Supplies"]),
        ("anna-bhagya", "food grains", "What benefit does Anna Bhagya provide?", "easy", ["food grains", "ration card"]),
        ("anna-bhagya", "valid Karnataka ration card", "What card must a household hold for Anna Bhagya?", "easy", ["Karnataka ration card"]),
        ("anna-bhagya", "food.karnataka.gov.in", "Which Food Department portal is listed for Anna Bhagya?", "easy", ["food.karnataka.gov.in"]),
        ("pmsby", "Pradhan Mantri Suraksha Bima", "What is the official name of PMSBY?", "easy", ["Pradhan Mantri Suraksha Bima Yojana"]),
        ("pmsby", "Department of Financial Services", "Which department administers PMSBY?", "easy", ["Department of Financial Services"]),
        ("pmsby", "Accidental death: Rs 2 lakh", "What sum insured does PMSBY list for accidental death?", "easy", ["2 lakh", "Accidental death"]),
        ("pmsby", "Permanent total disability", "What sum insured does PMSBY list for permanent total disability due to accident?", "easy", ["2 lakh", "Permanent total disability"]),
        ("pmsby", "Permanent partial disability", "What sum insured does PMSBY list for permanent partial disability due to accident?", "easy", ["1 lakh", "Permanent partial disability"]),
        ("pmsby", "Rs 20 per member", "What annual premium does the PMSBY note list?", "easy", ["Rs 20"]),
        ("pmsby", "auto-debited", "How is the PMSBY premium typically collected?", "easy", ["auto-debit"]),
        ("pmsby", "18 to 70", "What age band does the PMSBY note describe as commonly notified?", "medium", ["18", "70"]),
        ("pmsby", "savings bank account", "What bank requirement does PMSBY list?", "easy", ["savings bank account"]),
        ("pmsby", "participating banks", "How does a citizen enroll in PMSBY according to the note?", "easy", ["participating banks"]),
        ("gruha-lakshmi", "Gruha Lakshmi", "What is the name of the Karnataka women income-support scheme in the seed note?", "easy", ["Gruha Lakshmi"]),
        ("gruha-lakshmi", "Rs 2,000", "How much monthly assistance does Gruha Lakshmi provide to an eligible woman head of family?", "easy", ["2,000"]),
        ("gruha-lakshmi", "Direct Benefit Transfer", "How is Gruha Lakshmi assistance transferred?", "easy", ["bank account", "DBT"]),
        ("gruha-lakshmi", "resident of Karnataka", "Must a Gruha Lakshmi applicant be a Karnataka resident according to the note?", "easy", ["resident of Karnataka"]),
        ("gruha-lakshmi", "head of the family", "What family status does Gruha Lakshmi require for the woman applicant?", "medium", ["head of the family"]),
        ("gruha-lakshmi", "Aadhaar-linked bank account", "What bank-account linkage does Gruha Lakshmi require?", "easy", ["Aadhaar-linked bank account"]),
        ("gruha-lakshmi", "Only one woman per family", "How many women per family are generally eligible for Gruha Lakshmi?", "medium", ["one woman per family"]),
        ("gruha-lakshmi", "sevasindhu.karnataka.gov.in", "Through which portal are Gruha Lakshmi applications commonly submitted?", "easy", ["Seva Sindhu"]),
        ("gruha-lakshmi", "Aadhaar", "Which identity document is listed as commonly required for Gruha Lakshmi?", "easy", ["Aadhaar"]),
    ]
    cases: List[Dict[str, Any]] = []
    n = 0
    for scheme, contains, question, difficulty, phrases in specs:
        item = _find(excerpts, scheme, contains=contains)
        if not item:
            continue
        n += 1
        cases.append(
            _factual_from_excerpt(
                f"gsb1-f{n:03d}",
                scheme,
                difficulty,
                question,
                item,
                excerpts_by_id,
                extra_phrases=phrases,
            )
        )
    return cases


def generate_eligibility(excerpts: List[Dict[str, Any]], excerpts_by_id: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = [
        ("shakti", "Women citizens of Karnataka", "A woman resident of Karnataka wants free travel on a participating KSRTC bus. Is she in the intended Shakti beneficiary group?", "eligible", {"is_woman": True, "state_karnataka": True}, "easy", ["Women", "Karnataka"]),
        ("shakti", "Men are not eligible", "A man in Karnataka asks for free Shakti bus travel. Is he eligible?", "ineligible", {"is_man": True, "state_karnataka": True, "is_woman": False}, "easy", ["Men are not eligible"]),
        ("shakti", "Women citizens of Karnataka", "A woman who lives in Maharashtra asks for Shakti free bus travel in Karnataka. Is she in the intended beneficiary group described in the note?", "ineligible", {"is_woman": True, "state_karnataka": False}, "medium", ["Women citizens of Karnataka"]),
        ("shakti", "Women citizens of Karnataka", "A woman citizen of Karnataka boards a participating notified state bus. Does the note treat her as an intended Shakti beneficiary?", "eligible", {"is_woman": True, "state_karnataka": True, "notified_bus": True}, "easy", ["Women citizens of Karnataka"]),
        ("shakti", "photo identity", "A Karnataka woman eligible under Shakti did not bring ID. Does the note still describe women citizens as intended beneficiaries, with ID possibly requested?", "eligible", {"is_woman": True, "state_karnataka": True, "has_id_now": False}, "medium", ["identity"]),
        ("pmsby", "18 to 70", "An Indian citizen aged 35 with a savings account and auto-debit consent asks about PMSBY. Does the note describe this profile as within the common eligibility conditions?", "eligible", {"age": 35, "age_in_common_band": True, "has_savings_bank": True, "auto_debit_consent": True}, "easy", ["18", "70"]),
        ("pmsby", "18 to 70", "A 16-year-old with a savings account asks to enroll in PMSBY. Is this age inside the commonly published 18-70 band?", "ineligible", {"age": 16, "age_in_common_band": False, "has_savings_bank": True}, "easy", ["18 to 70"]),
        ("pmsby", "18 to 70", "A 75-year-old with a savings account asks to enroll in PMSBY. Is this age inside the commonly published 18-70 band?", "ineligible", {"age": 75, "age_in_common_band": False, "has_savings_bank": True}, "easy", ["18 to 70"]),
        ("pmsby", "savings bank account", "A 40-year-old Indian citizen has no savings bank account. Does the PMSBY note treat a savings account as required?", "ineligible", {"age": 40, "age_in_common_band": True, "has_savings_bank": False}, "medium", ["savings bank account"]),
        ("pmsby", "18 to 70", "A citizen who just turned 18 has a savings account and auto-debit consent. Is age 18 inside the commonly published PMSBY band?", "eligible", {"age": 18, "age_in_common_band": True, "has_savings_bank": True, "auto_debit_consent": True}, "hard", ["18 to 70"]),
        ("pmsby", "18 to 70", "A citizen aged 70 has a savings account and auto-debit consent. Is age 70 inside the commonly published PMSBY band?", "eligible", {"age": 70, "age_in_common_band": True, "has_savings_bank": True, "auto_debit_consent": True}, "hard", ["18 to 70"]),
        ("gruha-lakshmi", "resident of Karnataka", "A woman who is a Karnataka resident, head of her family, with an Aadhaar-linked bank account asks about Gruha Lakshmi. Does this match the listed conditions?", "eligible", {"is_woman": True, "state_karnataka": True, "is_head_of_family": True, "aadhaar_linked_bank": True}, "easy", ["resident of Karnataka"]),
        ("gruha-lakshmi", "Woman must be a resident", "A man who is a Karnataka resident and head of family asks for Gruha Lakshmi. Is he eligible under the listed rules?", "ineligible", {"is_woman": False, "is_man": True, "state_karnataka": True, "is_head_of_family": True}, "easy", ["Woman"]),
        ("gruha-lakshmi", "resident of Karnataka", "A woman living in Tamil Nadu asks for Gruha Lakshmi. Does the note require Karnataka residence?", "ineligible", {"is_woman": True, "state_karnataka": False, "is_head_of_family": True}, "medium", ["resident of Karnataka"]),
        ("gruha-lakshmi", "head of the family", "A Karnataka woman with an Aadhaar-linked bank account is not the head of the family. Does the note require head-of-family status?", "ineligible", {"is_woman": True, "state_karnataka": True, "is_head_of_family": False, "aadhaar_linked_bank": True}, "medium", ["head of the family"]),
        ("gruha-lakshmi", "Aadhaar-linked bank account", "A Karnataka woman head of family has no Aadhaar-linked bank account. Does the note require that account?", "ineligible", {"is_woman": True, "state_karnataka": True, "is_head_of_family": True, "aadhaar_linked_bank": False}, "medium", ["Aadhaar-linked bank account"]),
        ("gruha-lakshmi", "Only one woman per family", "A second woman in a family already receiving Gruha Lakshmi asks to enroll. Is a second woman generally eligible?", "ineligible", {"is_woman": True, "state_karnataka": True, "is_head_of_family": True, "aadhaar_linked_bank": True, "another_woman_already_beneficiary": True}, "hard", ["Only one woman per family"]),
        ("pmfby", "notified crops in notified areas", "A farmer growing a notified crop in a notified area asks about PMFBY enrollment. Does the note include this farmer?", "eligible", {"is_farmer": True, "crop_notified": True, "area_notified": True}, "easy", ["notified crops", "notified areas"]),
        ("pmfby", "Coverage applies only for crops and areas notified", "A farmer grows a crop that is not notified for this season. Does PMFBY coverage apply?", "ineligible", {"is_farmer": True, "crop_notified": False, "area_notified": True}, "medium", ["notified"]),
        ("pmfby", "loanee and", "A loanee farmer growing a notified crop in a notified area asks about PMFBY. May loanee farmers enroll?", "eligible", {"is_farmer": True, "crop_notified": True, "area_notified": True, "is_loanee": True}, "medium", ["loanee"]),
        ("pmfby", "non-loanee", "A non-loanee farmer growing a notified crop in a notified area asks about PMFBY. May non-loanee farmers enroll?", "eligible", {"is_farmer": True, "crop_notified": True, "area_notified": True, "is_loanee": False}, "medium", ["non-loanee"]),
        ("pmfby", "All farmers growing notified crops", "A person who is not growing any crop asks to enroll in PMFBY. Does the note describe this person as an eligible farmer?", "ineligible", {"is_farmer": False, "crop_notified": False, "area_notified": False}, "easy", ["farmers growing notified crops"]),
        ("anna-bhagya", "valid Karnataka ration card", "A household holds a valid Karnataka ration card. Does the Anna Bhagya note treat this as the required eligibility document?", "eligible", {"has_karnataka_ration_card": True}, "easy", ["Karnataka ration card"]),
        ("anna-bhagya", "valid Karnataka ration card", "A household has no ration card. Is Anna Bhagya eligibility described as available?", "ineligible", {"has_karnataka_ration_card": False}, "easy", ["ration card"]),
        ("anna-bhagya", "valid Karnataka ration card", "A household holds only a ration card issued in another state. Does the note require a Karnataka ration card?", "ineligible", {"has_karnataka_ration_card": False, "has_other_state_ration_card": True}, "medium", ["Karnataka ration card"]),
    ]
    cases: List[Dict[str, Any]] = []
    for i, (scheme, contains, question, status, profile, difficulty, phrases) in enumerate(rows, start=1):
        item = _find(excerpts, scheme, contains=contains)
        if not item:
            continue
        extra = _find(excerpts, scheme, field="eligibility")
        evidence_ids = _ids(item, extra if extra and extra["id"] != item["id"] else None)
        cases.append(
            _case(
                cid=f"gsb1-e{i:03d}",
                scheme=scheme,
                category="eligibility",
                difficulty=difficulty,
                language="en",
                question=question,
                expected_behavior=status,
                excerpts_by_id=excerpts_by_id,
                evidence_ids=evidence_ids,
                ground_truth={
                    "facts": [item["excerpt"]],
                    "required_keyphrases": phrases,
                    "eligibility_status": status,
                    "citizen_profile": profile,
                },
            )
        )
    return cases


def generate_unsupported(excerpts: List[Dict[str, Any]], excerpts_by_id: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Questions whose requested claim is not present in the selected seed evidence."""
    corpus_ids = _ids(
        _find(excerpts, "pmfby", field="purpose"),
        _find(excerpts, "shakti", field="purpose"),
        _find(excerpts, "pmsby", field="benefits"),
        _find(excerpts, "gruha-lakshmi", field="benefits"),
        _find(excerpts, "anna-bhagya", field="benefits"),
    )
    specs = [
        ("none", "How much money does PM-Kisan pay each installment?", ["6000", "₹6,000", "rs 2000 installment", "2,000 per installment"], "adversarial"),
        ("none", "How many free electricity units does Gruha Jyothi give every month?", ["200 units", "200 units free"], "adversarial"),
        ("none", "What monthly allowance does Yuva Nidhi pay unemployed graduates?", ["3000", "1,500", "yuva nidhi rupees"], "adversarial"),
        ("shakti", "Does the Shakti scheme pay women a monthly cash grant of Rs 2,000?", ["monthly cash", "2000", "2,000"], "adversarial"),
        ("pmsby", "Does PMSBY pay Rs 2 lakh for death due to illness, not an accident?", ["illness", "natural death", "disease"], "adversarial"),
        ("pmfby", "What is the exact farmer premium percentage for PMFBY Kharif 2024 in Karnataka?", ["1.5%", "2%", "kharif 2024"], "hard"),
        ("anna-bhagya", "Exactly how many kilograms of rice does Anna Bhagya give this month?", ["10 kg", "5 kg", "35 kg"], "hard"),
        ("none", "How many free LPG cylinders does Ujjwala provide each year?", ["free cylinder", "ujjwala"], "adversarial"),
        ("none", "What is the current MGNREGA daily wage in Karnataka?", ["wage", "309", "349"], "adversarial"),
        ("none", "What is the PMAY urban subsidy amount for a middle-income family?", ["2.67", "pmay subsidy"], "adversarial"),
        ("shakti", "Is Shakti free travel available on all private buses in Karnataka?", ["private bus", "all private"], "adversarial"),
        ("gruha-lakshmi", "Does Gruha Lakshmi pay Rs 2,000 to widower men who head a household?", ["widower", "men"], "adversarial"),
        ("pmsby", "Does PMSBY cover crop yield loss for farmers?", ["crop", "yield loss"], "adversarial"),
        ("none", "What fixed deposit amount does the Bhagyalakshmi scheme give at maturity?", ["1,00,000", "100000"], "adversarial"),
        ("none", "In which year will Jal Jeevan Mission finish every household tap connection?", ["2024", "2028"], "adversarial"),
    ]
    cases: List[Dict[str, Any]] = []
    for i, (scheme, question, forbidden, difficulty) in enumerate(specs, start=1):
        evidence_ids = corpus_ids
        if scheme != "none":
            hit = (
                _find(excerpts, scheme, field="benefits")
                or _find(excerpts, scheme, field="purpose")
                or _find(excerpts, scheme, field="eligibility")
                or _find(excerpts, scheme)
            )
            evidence_ids = _ids(hit) if hit else corpus_ids
        cases.append(
            _case(
                cid=f"gsb1-u{i:03d}",
                scheme=scheme if scheme != "none" else "unspecified",
                category="unsupported",
                difficulty=difficulty,
                language="en",
                question=question,
                expected_behavior="unsupported",
                excerpts_by_id=excerpts_by_id,
                evidence_ids=evidence_ids,
                ground_truth={
                    "facts": [
                        "The requested numeric or categorical claim is not stated in the selected seed evidence."
                    ],
                    "must_not_assert": forbidden,
                    "eligibility_status": None,
                    "unsupported_claim": question,
                },
            )
        )
    return cases


_VALIDATED_TRANSLATIONS = [
    {
        "scheme": "pmsby",
        "contains": "Rs 20 per member",
        "en": "What is the annual premium listed for PMSBY?",
        "hi": "पीएमएसबीवाई की वार्षिक प्रीमियम राशि कितनी है?",
        "kn": "ಪಿಎಂಎಸ್‌ಬಿವೈ ವಾರ್ಷಿಕ ಪ್ರೀಮಿಯಂ ಎಷ್ಟು?",
        "phrases": ["20"],
        "difficulty": "easy",
    },
    {
        "scheme": "gruha-lakshmi",
        "contains": "Rs 2,000",
        "en": "How much monthly assistance does Gruha Lakshmi list for an eligible woman head of family?",
        "hi": "गृह लक्ष्मी योजना में पात्र महिला मुखिया को प्रति माह कितनी सहायता लिखी है?",
        "kn": "ಗೃಹ ಲಕ್ಷ್ಮಿ ಯೋಜನೆಯಲ್ಲಿ ಅರ್ಹ ಮಹಿಳಾ ಕುಟುಂಬ ಮುಖ್ಯಸ್ಥೆಗೆ ತಿಂಗಳಿಗೆ ಎಷ್ಟು ನೆರವು ಬರೆಯಲಾಗಿದೆ?",
        "phrases": ["2,000"],
        "difficulty": "easy",
    },
    {
        "scheme": "shakti",
        "contains": "Men are not eligible",
        "en": "Are men eligible for free travel under the Shakti scheme?",
        "hi": "क्या पुरुष शक्ति योजना के तहत मुफ्त यात्रा के पात्र हैं?",
        "kn": "ಶಕ್ತಿ ಯೋಜನೆಯಡಿ ಪುರುಷರು ಉಚಿತ ಪ್ರಯಾಣಕ್ಕೆ ಅರ್ಹರೇ?",
        "phrases": ["not eligible"],
        "difficulty": "easy",
    },
    {
        "scheme": "anna-bhagya",
        "contains": "valid Karnataka ration card",
        "en": "What card does the Anna Bhagya note require?",
        "hi": "अन्न भाग्य नोट के अनुसार कौन-सा कार्ड आवश्यक है?",
        "kn": "ಅನ್ನ ಭಾಗ್ಯ ಟಿಪ್ಪಣಿಯ ಪ್ರಕಾರ ಯಾವ ಕಾರ್ಡ್ ಬೇಕು?",
        "phrases": ["ration card"],
        "difficulty": "easy",
    },
    {
        "scheme": "pmfby",
        "contains": "Ministry of Agriculture",
        "en": "Which ministry administers PMFBY according to the scheme note?",
        "hi": "योजना नोट के अनुसार पीएमएफबीवाई किस मंत्रालय के अंतर्गत है?",
        "kn": "ಯೋಜನಾ ಟಿಪ್ಪಣಿಯ ಪ್ರಕಾರ ಪಿಎಂಎಫ್‌ಬಿವೈ ಯಾವ ಸಚಿವಾಲಯದ ಅಡಿಯಲ್ಲಿದೆ?",
        "phrases": ["Agriculture"],
        "difficulty": "easy",
    },
]


def generate_multilingual(excerpts: List[Dict[str, Any]], excerpts_by_id: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    n = 0
    for spec in _VALIDATED_TRANSLATIONS:
        item = _find(excerpts, spec["scheme"], contains=spec["contains"])
        if not item:
            continue
        for lang in ("hi", "kn"):
            n += 1
            cases.append(
                _case(
                    cid=f"gsb1-m{n:03d}",
                    scheme=spec["scheme"],
                    category="multilingual",
                    difficulty=spec["difficulty"],
                    language=lang,
                    question=spec[lang],
                    expected_behavior="answer_from_evidence",
                    excerpts_by_id=excerpts_by_id,
                    evidence_ids=[item["id"]],
                    ground_truth={
                        "facts": [item["excerpt"]],
                        "required_keyphrases": spec["phrases"],
                        "english_source_question": spec["en"],
                        "translation_validated": True,
                    },
                    extra={"translation": {"source_language": "en", "validated": True, "source_question": spec["en"]}},
                )
            )
    return cases


def generate_difficult(excerpts: List[Dict[str, Any]], excerpts_by_id: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = [
        (
            "pmfby",
            "Coverage applies only for crops and areas notified",
            "A farmer's village is notified but the crop is not notified this season. Does PMFBY coverage apply?",
            "ineligible",
            "hard",
            ["notified"],
            "answer_from_evidence",
        ),
        (
            "pmsby",
            "18 to 70",
            "Is a person who is exactly 18 years old inside the commonly published PMSBY age band?",
            "eligible",
            "hard",
            ["18"],
            "eligible",
        ),
        (
            "pmsby",
            "18 to 70",
            "Is a person who is exactly 70 years old inside the commonly published PMSBY age band?",
            "eligible",
            "hard",
            ["70"],
            "eligible",
        ),
        (
            "gruha-lakshmi",
            "Only one woman per family",
            "Can two women in the same family both receive Gruha Lakshmi under the general norm in the note?",
            "ineligible",
            "hard",
            ["one woman per family"],
            "ineligible",
        ),
        (
            "shakti",
            "premium or excluded services",
            "Do Shakti zero-fare rules automatically cover every premium or excluded bus service?",
            None,
            "hard",
            ["notification"],
            "check_official_notification",
        ),
        (
            "pmfby",
            "season-specific",
            "What is this season's exact PMFBY sum insured for a one-hectare paddy plot in Mysuru?",
            None,
            "hard",
            ["season-specific"],
            "check_official_notification",
        ),
        (
            "anna-bhagya",
            "Quantity and price",
            "What exact rice quantity does Anna Bhagya provide this month?",
            None,
            "hard",
            ["notifications"],
            "check_official_notification",
        ),
        (
            "pmsby",
            "One cover per eligible member",
            "Can one eligible member hold multiple PMSBY covers through different participating banks according to the note?",
            "ineligible",
            "hard",
            ["One cover"],
            "answer_from_evidence",
        ),
        (
            "gruha-lakshmi",
            "head of the family",
            "A Karnataka woman has Aadhaar-linked banking but is not recognized as head of the family. Does the listed Gruha Lakshmi rule set treat her as eligible?",
            "ineligible",
            "hard",
            ["head of the family"],
            "ineligible",
        ),
        (
            "pmfby",
            "loanee and",
            "Do both loanee and non-loanee farmers growing notified crops in notified areas appear in the PMFBY enrollment description?",
            "eligible",
            "medium",
            ["loanee", "non-loanee"],
            "answer_from_evidence",
        ),
    ]
    cases: List[Dict[str, Any]] = []
    for i, (scheme, contains, question, status, difficulty, phrases, behavior) in enumerate(rows, start=1):
        item = _find(excerpts, scheme, contains=contains)
        if not item:
            continue
        cases.append(
            _case(
                cid=f"gsb1-d{i:03d}",
                scheme=scheme,
                category="difficult",
                difficulty=difficulty,
                language="en",
                question=question,
                expected_behavior=behavior,
                excerpts_by_id=excerpts_by_id,
                evidence_ids=[item["id"]],
                ground_truth={
                    "facts": [item["excerpt"]],
                    "required_keyphrases": phrases,
                    "eligibility_status": status,
                    "citizen_profile": None,
                },
            )
        )
    return cases


def _select_quota(cases: List[Dict[str, Any]], quota: int) -> List[Dict[str, Any]]:
    seen = set()
    chosen: List[Dict[str, Any]] = []
    for case in cases:
        key = (case["language"], normalize_question(case["question"]))
        if key in seen:
            continue
        seen.add(key)
        chosen.append(case)
        if len(chosen) >= quota:
            break
    return chosen


def generate_candidates(excerpts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    excerpts_by_id = excerpt_index(excerpts)
    buckets = {
        "factual": generate_factual(excerpts, excerpts_by_id),
        "eligibility": generate_eligibility(excerpts, excerpts_by_id),
        "unsupported": generate_unsupported(excerpts, excerpts_by_id),
        "multilingual": generate_multilingual(excerpts, excerpts_by_id),
        "difficult": generate_difficult(excerpts, excerpts_by_id),
    }
    selected: List[Dict[str, Any]] = []
    for category, quota in TARGET_QUOTAS.items():
        selected.extend(_select_quota(buckets[category], quota))
    return selected
