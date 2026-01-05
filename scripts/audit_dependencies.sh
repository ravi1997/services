#!/bin/bash
# Security Audit Helper Script

set -e

echo "============================================="
echo "🔒 Starting Security Audit: $(date)"
echo "============================================="

# 1. Dependency Vulnerability Check
echo "🔍 Checking dependencies with pip-audit..."
if command -v pip-audit &> /dev/null; then
  pip-audit
  echo "✅ pip-audit: PASSED"
else
  echo "⚠️ pip-audit not installed!"
  exit 1
fi

echo "---------------------------------------------"

# 2. Safety Check
echo "🔍 Checking dependencies with safety..."
if command -v safety &> /dev/null; then
  safety check
  echo "✅ safety: PASSED"
else
  echo "⚠️ safety not installed!"
fi

echo "---------------------------------------------"
echo "🎉 Security Audit Complete!"
exit 0
