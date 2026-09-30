# Supported stock locomotives

The application supports Railroader's 21 stock steam locomotives. Their identifiers, source facts, reviewed defaults, measurement data, and source fingerprints are maintained in `src/rr2dv/stock_locos.json`.

The app validates this table before using it. Each record includes its evidence and basis. When installed source files do not match the recorded fingerprints, the app identifies the game build as unknown and avoids applying fingerprint-dependent measurements.

The table informs review defaults and measured geometry. User-reviewed values and source definitions remain authoritative when they disagree with a suggestion.
