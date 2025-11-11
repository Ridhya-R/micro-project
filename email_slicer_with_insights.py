# email_slicer_dashboard.py
import streamlit as st
import re
from datetime import datetime
import io
import matplotlib.pyplot as plt
import hashlib
import pandas as pd
import tempfile
import os

# Optional PDF support (reportlab). If not installed, PDF export will be disabled gracefully.
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

# ------------------------------
# Helper functions
# ------------------------------
def get_greeting():
    now = datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        return "Good morning 🌅"
    if 12 <= hour < 17:
        return "Good afternoon ☀"
    if 17 <= hour < 21:
        return "Good evening 🌇"
    return "Hello there 🌙"

def validate_email(email: str) -> bool:
    """
    Reasonable email validation regex (not full RFC).
    Accepts + aliases and many real-world variants.
    """
    if not email or "@" not in email:
        return False
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email.strip()))

def parse_email(email: str):
    """
    Returns username, domain_full, domain_name (first label), extension (last label)
    """
    email = email.strip()
    username, domain_full = email.split("@", 1)
    domain_parts = domain_full.split(".")
    domain_name = domain_parts[0] if domain_parts else domain_full
    extension = domain_parts[-1] if len(domain_parts) > 1 else ""
    return username, domain_full, domain_name, extension

def provider_insights(domain_full: str):
    domain = domain_full.lower()
    mapping = {
        "gmail.com": ("Google Mail", "Free/Consumer", "Popular personal email provider (Gmail)."),
        "googlemail.com": ("Google Mail", "Free/Consumer", "Alias for Gmail."),
        "yahoo.com": ("Yahoo Mail", "Free/Consumer", "Popular consumer email provider."),
        "outlook.com": ("Microsoft Outlook", "Free/Consumer", "Microsoft consumer email service."),
        "hotmail.com": ("Microsoft Hotmail/Outlook", "Free/Consumer", "Legacy Hotmail (now Outlook)."),
        "live.com": ("Microsoft Live/Outlook", "Free/Consumer", "Microsoft's Live/Outlook domains."),
        "protonmail.com": ("Proton Mail", "Privacy-focused", "End-to-end encrypted email service."),
        "icloud.com": ("Apple iCloud Mail", "Free/Consumer", "Apple's consumer email service."),
        "zoho.com": ("Zoho Mail", "Business/SMB", "Often used for small-business/custom domains."),
        "aol.com": ("AOL Mail", "Free/Consumer", "Legacy consumer email provider."),
        "mail.com": ("mail.com", "Free/Consumer", "Consumer email service with multiple domain choices."),
        "gmx.com": ("GMX Mail", "Free/Consumer", "European consumer email provider."),
    }
    for key, val in mapping.items():
        if domain == key or domain.endswith("." + key):
            return {"provider_name": val[0], "provider_type": val[1], "notes": val[2]}
    if domain.endswith(".edu"):
        return {"provider_name": "Educational (edu)", "provider_type": "Institutional", "notes": "Typically a university/college email."}
    if domain.endswith(".gov"):
        return {"provider_name": "Government (gov)", "provider_type": "Institutional", "notes": "Government domain."}
    return {"provider_name": "Custom / Organization", "provider_type": "Custom/Business", "notes": "Could be a company or self-hosted email. Provider-specific features unknown."}

# Email type detector
def detect_email_type(domain_full: str):
    d = domain_full.lower()
    personal_keywords = ["gmail", "yahoo", "hotmail", "outlook", "icloud", "aol", "protonmail", "gmx", "mail.com", "zoho"]
    if any(k in d for k in personal_keywords):
        return "Personal Email"
    if d.endswith((".edu", ".ac.in", ".edu.in")):
        return "Educational / Academic Email"
    if d.endswith(".gov"):
        return "Government Email"
    return "Business / Organizational Email"

# TLD info (small mapping, extendable)
TLD_INFO = {
    "com": "Commercial (global)",
    "org": "Organization (non-profit)",
    "net": "Network / ISP",
    "edu": "Educational institutions",
    "gov": "Government",
    "in": "India (country code TLD)",
    "uk": "United Kingdom (country code TLD)",
    "us": "United States (country code TLD)",
    "ca": "Canada (country code TLD)",
    "au": "Australia (country code TLD)",
}

def tld_info(extension):
    if not extension:
        return "No TLD / local"
    return TLD_INFO.get(extension.lower(), "Unknown or custom TLD")

# Common typos suggestions
COMMON_FIXES = {
    "gamil.com": "gmail.com",
    "gmai.com": "gmail.com",
    "gmal.com": "gmail.com",
    "yaho.com": "yahoo.com",
    "hotnail.com": "hotmail.com",
    "outlok.com": "outlook.com",
    "gnail.com": "gmail.com",
}

def suggest_fix(domain_full):
    return COMMON_FIXES.get(domain_full.lower(), None)

def fake_creation_year(email):
    # deterministic pseudo-random "creation year" for fun
    h = int(hashlib.md5(email.encode()).hexdigest(), 16)
    return 2000 + (h % 25)  # year between 2000 - 2024 (change range if desired)

# Report building
def make_report(original_email, username, domain_full, domain_name, extension, lengths, provider_info, email_type, tld_description, timestamp):
    lines = []
    lines.append("Email Slicer with Insights — Detailed Report")
    lines.append(f"Generated: {timestamp}")
    lines.append("-" * 48)
    lines.append(f"Original email: {original_email}")
    lines.append("")
    lines.append("Extracted components:")
    lines.append(f"  Username       : {username}")
    lines.append(f"  Domain (full)  : {domain_full}")
    lines.append(f"  Domain (label) : {domain_name}")
    lines.append(f"  Extension      : {extension}")
    lines.append("")
    lines.append("Character counts:")
    lines.append(f"  Username length: {lengths['username']}")
    lines.append(f"  Domain length  : {lengths['domain_full']}")
    lines.append(f"  Extension len  : {lengths['extension']}")
    lines.append("")
    lines.append("Inferred provider information:")
    lines.append(f"  Provider name : {provider_info['provider_name']}")
    lines.append(f"  Provider type : {provider_info['provider_type']}")
    lines.append(f"  Notes         : {provider_info['notes']}")
    lines.append("")
    lines.append(f"Email type classification: {email_type}")
    lines.append(f"TLD info: .{extension} → {tld_description}")
    lines.append("")
    lines.append("Notes & caveats:")
    lines.append("  - Extension parsing treats the last domain label as the extension (e.g., 'uk' in 'example.co.uk').")
    lines.append("  - For multi-level TLDs (co.uk, ac.in etc.) or specialized hosting, the provider name may be 'Custom / Organization'.")
    lines.append("  - This report does not perform live DNS/MX lookups or verify mailbox existence.")
    lines.append("")
    lines.append("Thank you for using Email Slicer with Insights! 🚀")
    return "\n".join(lines)

def make_pdf_bytes(report_text):
    """
    Create a PDF in-memory and return bytes. Requires reportlab.
    """
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("reportlab not available")
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(temp.name, pagesize=letter)
    width, height = letter
    left_margin = 40
    y = height - 40
    for line in report_text.split("\n"):
        # Draw text; if out of space, start new page
        c.drawString(left_margin, y, line)
        y -= 12
        if y < 40:
            c.showPage()
            y = height - 40
    c.save()
    with open(temp.name, "rb") as f:
        pdf_bytes = f.read()
    try:
        os.unlink(temp.name)
    except Exception:
        pass
    return pdf_bytes

# ------------------------------
# Streamlit UI
# ------------------------------
st.set_page_config(page_title="Email Slicer with Insights", page_icon="📧", layout="centered")
st.title("📧 Email Slicer with Insights")
st.write(get_greeting() + " — enter any email address below to analyze it.")

st.markdown(
    """
    **What this app does**
    - Validates email format & extracts username / domain / extension  
    - Identifies common email providers and classifies email type  
    - Suggests fixes for common typos  
    - Shows charts comparing parts and composition  
    - Bulk analysis mode for multiple emails  
    - Download detailed TXT report (PDF if available)
    """
)

st.write("---")

# Two-column main input: single email (left) and bulk input (right)
col_left, col_right = st.columns([2, 3])

with col_left:
    st.subheader("🔎 Single Email Analysis")
    default_example = "ridhyar.@gmail.com"
    email_input = st.text_input("Enter an email address", value=default_example, help="e.g., name@example.com")
    analyze_btn = st.button("Analyze Email")

with col_right:
    st.subheader("📋 Bulk Email Analysis (one per line)")
    bulk_input = st.text_area("Paste multiple emails here", height=140, placeholder="user1@example.com\nuser2@company.org")
    analyze_bulk_btn = st.button("Analyze All")

# Handle single analysis
if analyze_btn:
    email = email_input.strip()
    if not email:
        st.warning("Please enter an email address to proceed.")
    elif not validate_email(email):
        st.error("❌ That doesn't look like a valid email format. Please check and try again.")
        st.info("Example valid format: user.name+tag@example-domain.com")
    else:
        username, domain_full, domain_name, extension = parse_email(email)
        provider = provider_insights(domain_full)
        email_type = detect_email_type(domain_full)
        tld_description = tld_info(extension)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lengths = {
            "username": len(username),
            "domain_full": len(domain_full),
            "extension": len(extension)
        }

        st.success("✅ Email parsed successfully!")
        st.subheader("Extracted components")
        c1, c2 = st.columns([2, 3])
        with c1:
            st.write("**Username**")
            st.code(username)
            st.metric("Username length", lengths["username"])
        with c2:
            st.write("**Domain (full)**")
            st.code(domain_full)
            st.metric("Domain length", lengths["domain_full"])

        st.write("**Extension**")
        st.code(extension if extension else "(none)")
        st.metric("Extension length", lengths["extension"])

        st.write("---")
        st.subheader("Inferred provider & classification")
        st.write(f"**Provider name:** {provider['provider_name']}")
        st.write(f"**Provider type:** {provider['provider_type']}")
        st.write(f"**Notes:** {provider['notes']}")
        st.write(f"**Email type:** {email_type}")
        st.info(f"**TLD info:** .{extension} → {tld_description}")

        # Suggest fix if domain looks like a common typo
        fix = suggest_fix(domain_full)
        if fix:
            st.warning(f"Possible typo detected. Did you mean **{username}@{fix}**?")

        # Fun creation-year estimate
        st.write("")
        st.write(f"🕓 Estimated creation year (fun): **{fake_creation_year(email)}**")

        # Charts: bar chart and pie chart
        st.subheader("🔢 Character count comparison")
        fig, ax = plt.subplots(figsize=(6, 3.5))
        parts = ["Username", "Domain (full)", "Extension"]
        values = [lengths["username"], lengths["domain_full"], lengths["extension"]]
        bars = ax.bar(parts, values)
        ax.set_ylabel("Number of characters")
        ax.set_ylim(0, max(values + [3]) + 2)
        ax.set_title("Email part lengths")
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f"{int(height)}", xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=9)
        st.pyplot(fig)

        st.subheader("📊 Email composition (by length)")
        fig2, ax2 = plt.subplots(figsize=(5, 4))
        sizes = values
        labels = parts
        # Avoid specifying colors per app rules — matplotlib will choose defaults
        ax2.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140)
        ax2.axis('equal')
        st.pyplot(fig2)

        # Build report and provide downloads
        report_text = make_report(
            original_email=email,
            username=username,
            domain_full=domain_full,
            domain_name=domain_name,
            extension=extension,
            lengths=lengths,
            provider_info=provider,
            email_type=email_type,
            tld_description=tld_description,
            timestamp=timestamp
        )
        safe_fname = f"email_slicer_report_{username}_{timestamp.replace(' ', '_').replace(':','')}.txt"
        st.download_button(
            label="📥 Download detailed report (TXT)",
            data=report_text,
            file_name=safe_fname,
            mime="text/plain"
        )

        if REPORTLAB_AVAILABLE:
            try:
                pdf_bytes = make_pdf_bytes(report_text)
                st.download_button(
                    label="📄 Download PDF report",
                    data=pdf_bytes,
                    file_name=safe_fname.replace(".txt", ".pdf"),
                    mime="application/pdf"
                )
            except Exception as e:
                st.error("PDF generation failed.")
                st.exception(e)
        else:
            st.info("PDF export is not available (install `reportlab` to enable).")

        st.write("---")
        st.subheader("Quick tips & notes")
        st.info(
            "This tool validates format and extracts components. It does not check whether the address actually receives mail "
            "(no MX/DNS checks here). For some domains, provider info may be generic (Custom / Organization)."
        )

# Handle bulk analysis
if analyze_bulk_btn:
    lines = [l.strip() for l in bulk_input.splitlines() if l.strip()]
    if not lines:
        st.warning("Please paste at least one email address for bulk analysis.")
    else:
        records = []
        for e in lines:
            valid = validate_email(e)
            if valid:
                u, d, n, x = parse_email(e)
                prov = provider_insights(d)
                etype = detect_email_type(d)
                rec = {
                    "original": e,
                    "username": u,
                    "domain": d,
                    "extension": x,
                    "username_len": len(u),
                    "domain_len": len(d),
                    "extension_len": len(x),
                    "provider": prov["provider_name"],
                    "type": etype,
                    "tld_info": tld_info(x),
                    "creation_year_est": fake_creation_year(e)
                }
            else:
                rec = {"original": e, "error": "Invalid format"}
            # suggest common fix if available
            if valid:
                fix = suggest_fix(d)
                rec["suggest_fix"] = f"{u}@{fix}" if fix else ""
            records.append(rec)
        df = pd.DataFrame(records)
        st.subheader("Bulk Analysis Results")
        # Show a table but also provide a CSV download
        st.dataframe(df)

        # CSV download
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download results as CSV", data=csv_bytes, file_name="bulk_email_analysis.csv", mime="text/csv")

        # Summary counts
        st.write("---")
        try:
            valid_count = df[df["error"].isna()].shape[0]
        except Exception:
            valid_count = sum(1 for r in records if "error" not in r)
        st.info(f"Processed {len(records)} rows — {valid_count} valid email(s).")

st.write("---")
st.caption("Built with ❤️ — Email Slicer with Insights. Enhance further by adding MX/DNS checks, domain WHOIS, or using email verification APIs for live mailbox checks.")
