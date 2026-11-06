# Release payload cleanup

The `clean` branch started from main commit `6465c0a`, the restricted 0.4.7 replacement. Its cleanup commit `de46021` was merged into local main on 6 November 2026 for 0.4.8. Existing releases and tags are unchanged.

Both generated release downloads now use a runtime tooling allowlist in `scripts/release_tooling.json`. It retains the shared Unity builder scripts, clip-path resolver and prefab dependency copier. Historical locomotive profiles, pilot preparation utilities, source-definition generators and the author-review packager are excluded from these downloads.

The three packaged stock, gauge and oil-fitting tables contain only the ten supported locomotives. Each retained profile is unchanged. The full development reference tables remain in the repository; validation accepts either the development table or the restricted runtime table. Blocked locomotive identifiers remain available for refusal messages.

Windows builds stage a fresh runtime payload before freezing. Packaging rejects Windows build directories containing legacy tooling or unrestricted reference tables, so an older build cannot silently bypass the cleanup. Catalogue pages remain included.

This policy applies to the generated Windows and Source release assets. GitHub's automatic source archives and repository history still represent the repository itself and retain developer references. No historic audit evidence is deleted or rewritten.

Original cleanup validation: 34 focused regression tests ran, 33 passed and one was skipped. The eight packaging tests passed, including staged runtime imports, table validation, exact preservation of the ten profiles, required tool presence, stale-payload rejection and nested archive rejection. Windows freezing was not performed during that original task. For 0.4.8, a fresh isolated build environment was prepared and Windows freezing plus its bundled self-test passed; see the current handover and retained release verification for the integrated validation. No replacement release was published by this preparation.
