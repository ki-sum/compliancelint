"""Log retention of "at least six months" (Art. 19(1) for providers, Art. 26(6) for deployers) as a number of days.

Six calendar months span 181 to 184 days (1 September to 1 March is 181 days, 1 July to 1 January is 184), so a period
counted in days keeps every log for at least six months, whatever the day it was written, only from 184 days. 180
days always falls short (found 2026-10-27; the modules had taken six months as 180 days). Texts checked by an
independent legal-check agent on 2026-10-27.
"""

RETENTION_MINIMUM_DAYS = 184


def six_months(article: str) -> str:
    """The minimum, as the user reads it in a finding: the law's words first, then the number of days."""
    holder = "deployer" if article.startswith("Art. 26") else "provider"
    return (f"{article} requires the logs, to the extent they are under the {holder}'s control, to be kept for a "
            f"period appropriate to the intended purpose of the high-risk AI system, of at least six months, unless "
            f"provided otherwise in applicable Union or national law, in particular in Union law on the protection of "
            f"personal data; counted in days, that is at least {RETENTION_MINIMUM_DAYS} days, which covers any six "
            f"calendar months.")


def short_of_six_months(subject: str, days: int) -> str:
    """Why a retention below RETENTION_MINIMUM_DAYS falls short, as the user reads it in a finding."""
    if days < 181:
        return f"{subject} of {days} days is shorter than six months."
    return (f"{subject} of {days} days does not keep every log for six months: six calendar months last 181 to "
            f"184 days, so a log written on 1 July, for example, would be deleted before its six months end on "
            f"1 January.")
