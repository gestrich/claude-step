# Validate README Against Feature Guides

Validate that README.md is an accurate derivative of the feature guides.

## Instructions

1. Read all feature guides in `docs/feature-guides/`:
   - `how-it-works.md`
   - `setup.md`
   - `projects.md`
   - `notifications.md`
   - `troubleshooting.md`

2. Read `README.md`

3. Check for these issues:

   **Accuracy Issues:**
   - Information in README that contradicts the feature guides
   - Outdated details (different defaults, changed behavior, etc.)
   - Incorrect links to guides

   **Orphaned Details:**
   - Information in README that doesn't exist in any feature guide
   - README should be a condensed summary, not contain unique details
   - Exception: Development section (testing, contributing) can stay in README only

   **Missing Links:**
   - Each README section should link to its corresponding detailed guide
   - Check that "→ Full guide:" links are present and correct

   **Consistency:**
   - Terminology matches between README and guides
   - Code examples are consistent (same workflow format, same defaults)

4. Report findings:

   ```
   ## Validation Results

   ### ✅ Passing
   - [List what's correct]

   ### ⚠️ Issues Found
   - [List any problems with specific details]

   ### Recommendations
   - [Suggested fixes if any issues found]
   ```

5. If issues are found, ask whether to fix them.

## When to Run

Run this validation:
- After updating any feature guide
- After updating README.md
- Before major releases
- As part of documentation review
