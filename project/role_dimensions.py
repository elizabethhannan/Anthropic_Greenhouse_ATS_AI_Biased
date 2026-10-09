"""Independent function, research evidence, and title-based leadership dimensions.

No person names or inferred demographics are used. Historical employment titles
and current profile titles must be classified separately, not substituted.
"""

import re

from build_anthropic_analysis_tables import classify_role, normalized


LEADERSHIP_LEVELS = [
    "Individual Contributor", "Manager", "Senior Manager", "Lead", "Director",
    "Senior Director", "Head", "VP / SVP / EVP", "C-Suite / Executive",
    "Founder / Co-founder", "Unclear Leadership Level",
]


def leadership(title, source="title_name"):
    text = normalized(title)
    rules = [
        ("Founder / Co-founder", r"\b(?:co[ -]?)?founder\b"),
        ("C-Suite / Executive", r"\bchief (?!of staff\b)[\w &/-]+ officer\b|\b(?:ceo|cto|cfo|coo|ciso|cio|chro|cmo|cco)\b"),
        ("VP / SVP / EVP", r"\b(?:vice[ -]president|vp|svp|evp)\b"),
        ("C-Suite / Executive", r"\bpresident\b"),
        ("Senior Director", r"\b(?:senior|sr\.?) director\b"),
        ("Director", r"\bdirector\b"),
        ("Head", r"\bhead (?:of\b|gtm\b)"),
        ("Senior Manager", r"\b(?:senior|sr\.?) manager\b"),
        ("Manager", r"\bmanager\b"),
        ("Lead", r"\b(?:team )?lead\b"),
    ]
    # Mentioning the executive someone supports is not their own seniority.
    support = re.search(r"\b(?:assistant|advisor|adviser|office|chief of staff) (?:to|of)\b", text)
    if not support:
        for level, pattern in rules:
            match = re.search(pattern, text)
            if match:
                return {
                    "leadership_level": level,
                    "leadership_evidence": f"{source}={title!r}; explicit title term {match.group()!r}. Title level only; reporting structure not verified.",
                    "leadership_source": source,
                    "people_management_status": "Unverified - title signal only",
                }
    if not support and re.search(
        r"\b(?:member of (?:the )?technical staff|mts|engineer|scientist|researcher|"
        r"fellow|analyst|specialist|designer|developer|accountant|recruiter|"
        r"coordinator|counsel|consultant|architect|writer|intern|trainee)\b", text
    ) and not re.search(r"\b(?:leadership|management)\b", text):
        return {
            "leadership_level": "Individual Contributor",
            "leadership_evidence": f"{source}={title!r}; occupational title without an explicit leadership term. Provisional title-based IC classification.",
            "leadership_source": source,
            "people_management_status": "Not established",
        }
    return {
        "leadership_level": "Unclear Leadership Level",
        "leadership_evidence": f"{source}={title!r}; insufficient evidence to assign a leadership level.",
        "leadership_source": source,
        "people_management_status": "Not established",
    }


def functional(title_name, title_role, title_sub_role, research_label=None):
    label = research_label or classify_role(title_name, title_role, title_sub_role)
    status = {"research": "Research", "non_research": "Non-Research", "review_needed": "Insufficient Evidence"}[label["CLASSIFICATION_STATUS"]]
    title = normalized(title_name)
    role = normalized(title_role)
    sub = normalized(title_sub_role)
    combined = " | ".join((title, role, sub))
    if status == "Research":
        category, basis = "Research", "Existing title-based research classification, including Fellows Researcher."
    elif re.search(r"\bgtm\b|\bsales\b|\baccount executive\b", title) or role == "sales":
        category, basis = "Sales / GTM", "Explicit sales/GTM evidence."
    elif re.search(r"\brecruit\w*\b|\bpeople\b|\btalent\b|\bhuman resources\b", combined):
        category, basis = "People / Recruiting", "People or recruiting function."
    elif role == "legal" or re.search(r"\bcounsel\b|\blegal\b|\bcompliance\b|\bgrc\b", title):
        category, basis = "Legal / Compliance", "Legal or compliance function."
    elif role == "finance" or re.search(r"\bfinance\b|\baccounting\b|\bpayroll\b|\btax\b", title):
        category, basis = "Finance", "Finance function."
    elif role == "marketing" or re.search(r"\bmarketing\b|\bbrand\b|\bcommunications?\b|\bcommunictions\b", title):
        category, basis = "Marketing / Communications", "Marketing or communications function."
    elif role == "product" or re.search(r"\bproduct (?:manager|management|design|engineering|strategy|operations)\b", title):
        category, basis = "Product", "Explicit product function."
    elif re.search(r"\bsecurity\b|\bcybersecurity\b", combined):
        category, basis = "Security", "Security function; not automatically AI safety research."
    elif re.search(r"\bapplied ai\b|\bsolutions? architect\b|\bforward deployed\b", title) or role == "sales engineering":
        category, basis = "Applied AI", "Applied AI or deployment function; research responsibility not implied."
    elif re.search(r"\bdata science\b|\banalytics\b|\bdata engineering\b", combined) or role == "analyst":
        category, basis = "Data / Analytics", "Data or analytics function."
    elif role == "engineering" or re.search(r"\bmember of (?:the )?technical staff\b|\bmts\b|\bengineer\w*\b", title):
        category, basis = "Engineering - General / Unspecified", "Engineering function is established; generic engineering/MTS does not establish research responsibility."
    elif role == "support":
        category, basis = "Support", "Structured support function."
    elif role in {"operations", "fulfillment"}:
        category, basis = "Operations", "Structured operations or fulfillment function."
    elif role == "partnerships":
        category, basis = "Partnerships", "Structured partnerships function."
    elif status == "Non-Research":
        category, basis = "Other Non-Research", "Existing explicit non-research function."
    else:
        category, basis = "Unknown / Unspecified", "Function cannot be established from the available employment fields."
    return {"functional_category": category, "functional_evidence": basis, "research_status": status}


def profile_leadership(current_title, headline, current_company):
    """Current profile evidence only; never silently overwrite at-hire seniority."""
    if normalized(current_company) != "anthropic":
        result = leadership(None, "profile_not_confirmed_anthropic")
        result["leadership_evidence"] = "Current employer is not confirmed as exact Anthropic; profile leadership is not assigned to this employment."
        return result
    result = leadership(current_title, "current_title")
    if result["leadership_level"] == "Unclear Leadership Level" and headline:
        # A headline may describe earlier roles or several affiliations. Preserve
        # it for human review instead of assigning its highest title to Anthropic.
        result["leadership_evidence"] += f" Headline available for review: {headline!r}; employer/time attribution remains unverified."
    return result


def source_gender(value):
    """Map only an actual supplied gender field; never derive it from names."""
    text = normalized(value)
    if text in {"male", "man", "m"}:
        return "Men"
    if text in {"female", "woman", "f"}:
        return "Women"
    if not text or text in {"unknown", "unclassified", "unspecified", "not specified", "prefer not to say", "null", "none"}:
        return "Unknown / Unclassified"
    return "Other / Source-reported"
