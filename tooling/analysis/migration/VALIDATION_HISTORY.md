# Validation history

- Nine Python workflow tests and eight actual Unity editor checks passed after relocation.
- Initial current-profile bundle audits passed with the exact reference warning lines.
- The new full-object parity reader initially needed support for ScriptableObjects without GameObjects and for RectTransform hierarchies. Those reader defects were corrected without changing bundle content.
- Frozen G29's legacy exporter writes a report and pack but no result.json. The first driver marked that exported run failed because it expected the newer completion format. The launcher now verifies its legacy completion evidence and requires full parity; a fresh migration_frozen02 run exercises that path. build-matrix.json preserves the initial driver outcome.
- Frozen G29's initial parity differences were external-file directory indices reordered between Library/unity default resources and Resources/unity_builtin_extra. Raw shader evidence is retained in shaders-old.json/shaders-new.json. Comparator v2 maps indices to external path/GUID/type and preserves built-in object IDs. No mesh/shader content checks were suppressed.
- Eight installer/rollback checks ran only against analysis/migration/installer-test-target. Additional empty-manifest rejection and valid-manifest acceptance checks passed. The intentionally invalid migration_installer_bad_fixture is labelled EXPECTED_FAILURE.txt and must not be treated as a real build.
- E04 is a confirmed pre-existing physics ledger discrepancy, preserved during relocation. No game installation or game/VR test occurred during this migration.
