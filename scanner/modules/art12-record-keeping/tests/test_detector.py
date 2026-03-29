"""Tests for Art. 12 Record-keeping detector."""

import os
import tempfile
import shutil
import json

# Add parent to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from detector import (
    scan_project,
    detect_language,
    scan_python_logging,
    scan_python_endpoints,
    scan_structured_fields,
    ComplianceLevel,
)


def create_test_project(files: dict[str, str]) -> str:
    """Create a temporary project directory with the given files."""
    tmpdir = tempfile.mkdtemp(prefix="cl_test_")
    for filepath, content in files.items():
        full_path = os.path.join(tmpdir, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
    return tmpdir


def test_no_logging():
    """Project with no logging should be NON_COMPLIANT."""
    project = create_test_project({
        "app.py": '''
from flask import Flask
app = Flask(__name__)

@app.route("/predict")
def predict():
    result = model.predict(request.json)
    return {"result": result}
''',
    })
    try:
        result = scan_project(project)
        assert not result.has_logging_framework, "Should detect no logging framework"
        assert result.overall_level == ComplianceLevel.NON_COMPLIANT
        print("[PASS] test_no_logging")
    finally:
        shutil.rmtree(project)


def test_with_logging():
    """Project with structlog should detect the framework."""
    project = create_test_project({
        "app.py": '''
import structlog
from flask import Flask

logger = structlog.get_logger()
app = Flask(__name__)

@app.route("/predict")
def predict():
    logger.info("prediction_requested", user_id=request.user.id, action="predict")
    result = model.predict(request.json)
    logger.info("prediction_completed", user_id=request.user.id, result_hash=hash(result))
    return {"result": result}
''',
    })
    try:
        result = scan_project(project)
        assert result.has_logging_framework, "Should detect structlog"
        assert result.logging_framework_name == "structlog"
        assert result.logging_is_automatic, "Should detect automatic logging"
        print("[PASS] test_with_logging")
    finally:
        shutil.rmtree(project)


def test_endpoint_coverage():
    """Detect endpoints with and without logging."""
    project = create_test_project({
        "app.py": '''
import logging
from flask import Flask

logger = logging.getLogger(__name__)
app = Flask(__name__)

@app.route("/api/v1/predict")
def predict():
    logger.info("prediction requested")
    return {"result": "ok"}

@app.route("/api/v1/train")
def train():
    # No logging here!
    return {"status": "training"}

@app.post("/api/v1/delete")
def delete():
    # No logging here either!
    return {"status": "deleted"}
''',
    })
    try:
        result = scan_project(project)
        assert result.endpoints_found == 3, f"Should find 3 endpoints, got {result.endpoints_found}"
        assert result.endpoints_with_logging == 1, f"Should find 1 with logging, got {result.endpoints_with_logging}"
        assert result.logging_coverage_pct < 50, "Coverage should be under 50%"

        # Check that non-logged endpoints generate findings
        non_compliant = [f for f in result.findings if f["level"] == "non_compliant" and "Endpoint" in f["description"]]
        assert len(non_compliant) == 2, f"Should have 2 endpoint findings, got {len(non_compliant)}"
        print("[PASS] test_endpoint_coverage")
    finally:
        shutil.rmtree(project)


def test_structured_fields():
    """Detect structured log fields."""
    project = create_test_project({
        "app.py": '''
import structlog

logger = structlog.get_logger()

def handle_request(request):
    logger.info(
        "request_processed",
        timestamp=datetime.utcnow().isoformat(),
        user_id=request.user.id,
        action="classify",
        session_id=request.session_id,
        input_hash=hashlib.sha256(request.data).hexdigest(),
    )
''',
    })
    try:
        result = scan_project(project)
        assert "timestamp" in result.structured_fields_found
        assert "user_id" in result.structured_fields_found
        assert "action" in result.structured_fields_found
        assert "session_id" in result.structured_fields_found
        assert "input_hash" in result.structured_fields_found
        print("[PASS] test_structured_fields")
    finally:
        shutil.rmtree(project)


def test_retention_policy():
    """Detect log retention configuration."""
    project = create_test_project({
        "app.py": "import logging\nlogger = logging.getLogger()\nlogger.info('test')\n",
        "config/logging.yaml": '''
logging:
  level: INFO
  retention_days: 180
  rotate: daily
  max_age: 365d
''',
    })
    try:
        result = scan_project(project)
        assert result.retention_policy_found, "Should detect retention policy"
        print("[PASS] test_retention_policy")
    finally:
        shutil.rmtree(project)


def test_tamper_protection():
    """Detect tamper protection mechanisms."""
    project = create_test_project({
        "app.py": "import logging\nlogger = logging.getLogger()\nlogger.info('test')\n",
        "audit.py": '''
import hmac
import hashlib

class AuditLogger:
    """Tamper-proof audit trail with hash chain."""

    def __init__(self):
        self.previous_hash = b"genesis"

    def log(self, event):
        entry_hash = hmac.new(
            self.previous_hash,
            event.encode(),
            hashlib.sha256
        ).digest()
        self.previous_hash = entry_hash
        return {"event": event, "integrity_check": entry_hash.hex()}
''',
    })
    try:
        result = scan_project(project)
        assert result.tamper_protection_found, "Should detect HMAC tamper protection"
        print("[PASS] test_tamper_protection")
    finally:
        shutil.rmtree(project)


def test_fully_compliant():
    """A well-instrumented project should be at least PARTIAL."""
    project = create_test_project({
        "app.py": '''
import structlog
from flask import Flask

logger = structlog.get_logger()
app = Flask(__name__)

@app.route("/api/predict")
def predict():
    logger.info("prediction", user_id="u123", action="predict",
                session_id="s456", timestamp="2026-01-01T00:00:00Z")
    return {"result": "ok"}
''',
        "config/logging.yaml": '''
retention_days: 180
rotate: daily
''',
        "audit.py": '''
# Hash chain for tamper-proof audit trail
import hmac
''',
    })
    try:
        result = scan_project(project)
        assert result.has_logging_framework
        assert result.overall_level != ComplianceLevel.NON_COMPLIANT, \
            f"Well-instrumented project should not be NON_COMPLIANT, got {result.overall_level}"
        print("[PASS] test_fully_compliant")
    finally:
        shutil.rmtree(project)


def test_language_detection():
    """Detect primary language correctly."""
    project = create_test_project({
        "main.py": "print('hello')",
        "utils.py": "def foo(): pass",
        "helper.py": "class Bar: pass",
        "index.js": "console.log('hi')",
    })
    try:
        lang = detect_language(project)
        assert lang == "python", f"Should detect Python, got {lang}"
        print("[PASS] test_language_detection")
    finally:
        shutil.rmtree(project)


def test_json_output():
    """Scan result should be serializable to JSON."""
    project = create_test_project({
        "app.py": "import logging\nlogger = logging.getLogger()\nlogger.info('test')\n",
    })
    try:
        result = scan_project(project)
        json_output = result.to_json()
        parsed = json.loads(json_output)
        assert "overall_level" in parsed
        assert "findings" in parsed
        assert "obligations" not in parsed  # obligations are in separate file
        print("[PASS] test_json_output")
    finally:
        shutil.rmtree(project)


if __name__ == "__main__":
    tests = [
        test_no_logging,
        test_with_logging,
        test_endpoint_coverage,
        test_structured_fields,
        test_retention_policy,
        test_tamper_protection,
        test_fully_compliant,
        test_language_detection,
        test_json_output,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1

    print(f"\n{'='*40}")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"{'='*40}")
