import structlog
from common.models import EnrichmentResult, FileObject, Finding, FindingCategory, FindingOrigin
from common.state_helpers import get_file_enriched

from file_enrichment_modules.module_loader import EnrichmentModule

logger = structlog.get_logger(module=__name__)


class FilenameScanner(EnrichmentModule):
    def __init__(self):
        super().__init__("filename_scanner")
        self.workflows = ["default"]

        # List of sensitive terms to check for in filenames
        self.sensitive_terms = [
            # Credentials & Authentication
            "password",
            "passwd",
            "secret",
            "credentials",
            "apikey",
            "api_key",
            "token",
            "oauth",
            "bearer",
            # Authentication info
            "login",
            "logon",
            "signin",
            "signon",
            "credential",
            "keytab",
            # Personal or confidential
            "confidential",
            "proprietary",
            "classified",
            "restricted",
            "sensitive",
            "internal",
            "private",
            # Web related
            "htaccess",
            "htpasswd",
            "wp-config",
            "phpinfo",
        ]

    def should_process(self, object_id: str) -> bool:
        """Always returns True as filename scanning should run on all files."""
        return True

    def process(self, object_id: str) -> EnrichmentResult | None:
        """Process file by checking its filename for sensitive terms."""
        try:
            # Get the current file_enriched from the database backend
            file_enriched = get_file_enriched(object_id)

            logger.debug(f"scanning filename of object_id: {object_id}, filename: {file_enriched.file_name}")

            matches = []
            filename_lower = file_enriched.file_name.lower()

            # Check each sensitive term against the filename
            for term in self.sensitive_terms:
                if term in filename_lower:
                    matches.append(term)

            # If we found sensitive terms in the filename
            if matches:
                enrichment_result = EnrichmentResult(module_name=self.name)

                # Create a display summary for the finding
                summary_markdown = self._create_summary_markdown(file_enriched.file_name, matches)
                display_data = FileObject(type="finding_summary", metadata={"summary": summary_markdown})

                # Create the finding
                finding = Finding(
                    category=FindingCategory.MISC,
                    finding_name="sensitive_filename",
                    origin_type=FindingOrigin.ENRICHMENT_MODULE,
                    origin_name=self.name,
                    object_id=file_enriched.object_id,
                    severity=4,
                    raw_data={"filename": file_enriched.file_name, "matches": matches},
                    data=[display_data],
                )

                enrichment_result.findings = [finding]
                enrichment_result.results = {"sensitive_terms": matches}

                return enrichment_result

            return None

        except Exception as e:
            logger.exception(e, message="Error in process()")
            return None

    def _create_summary_markdown(self, filename, matches):
        """Create a markdown summary of the finding."""
        markdown = [
            "# Sensitive Filename Detection",
            f"\nThe filename **{filename}** contains potentially sensitive terms:\n",
            "### Matches",
        ]

        for match in matches:
            markdown.append(f"- `{match}`")

        return "\n".join(markdown)


def create_enrichment_module() -> EnrichmentModule:
    return FilenameScanner()
