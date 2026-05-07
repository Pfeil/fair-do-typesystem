# FDO Type System Reconstruction

This folder contains a machine-readable reconstruction of the FDO type system as described in the [FDO Architecture Specification](../sections/).

## Files

| File | Description |
|------|-------------|
| `typesystem.yaml` | Complete reconstruction of the type system in YAML format |
| `visualize.py` | Python script to generate a graph visualization of the type system |

## Structure of `typesystem.yaml`

The YAML file is organized into these sections:

### `profiles`
The four pillar profiles that define meta-objects:
- `0.FDO/Root` — Minimal root profile (all FDOs must validate against it)
- `0.FDO/ProfileDef` — Template for all FDO profiles
- `0.FDO/AttributeDef` — Template for all attribute definitions
- `0.FDO/SyntaxDef` — Template for all syntax definitions

Each profile lists its `extends` chain and the `attributes` it declares (with cardinalities).

### `attribute_definitions`
All attribute definitions defined by the FDO Forum, grouped by their context:
- **Mandatory attributes**: `0.FDO/Type`, `0.FDO/Profile`, `0.FDO/Data`
- **Profile definition attributes**: `0.FDO/Name`, `0.FDO/Description`, `0.FDO/Attribute`, `0.FDO/Extends`, `0.FDO/denyAdditionalAttributes`
- **Attribute definition attributes**: `0.FDO/ValidationMechanism`, `0.FDO/DataType`, `0.FDO/Cardinality`
- **Syntax definition attributes**: `0.FDO/PrimitiveDataType`, `0.FDO/Regex`, `0.FDO/NumericInterval`, `0.FDO/Whitelist`, `0.FDO/Blacklist`
- **Type system attributes**: `0.FDO/DerivedFromType`

Each attribute definition includes its `validation_mechanism`, `data_type_refs`, and `cardinality_rule`.

### `validation_mechanisms`
The six validation mechanisms defined in the specification:
1. `Syntax` — Validate against a syntax definition
2. `Union` — "Any of" several attribute definitions
3. `InlineCombination` — "All of" several attribute definitions
4. `ProfileReference` — Reference to an FDO following a specific profile
5. `AttributeReference` — Redirect to another attribute in the same record
6. `ExternalVocabularyReference` — Reference to an external vocabulary namespace

### `fdo_types`
The special FDO types assigned to meta-objects:
- `FDO_Profile`
- `FDO_Attribute_Definition`
- `FDO_Syntax_Definition`
- `FDO_Type_Definition`

### `syntax_primitives`
The four primitive data types all clients must support: `string`, `number`, `integer`, `boolean`.

### `inferred_syntax_definitions`
Syntax definitions that are implied by attribute definitions but not explicitly defined in the specification. These are marked as inferred for clarity.

### `graph_edges`
An explicit edge list for graph visualization. Edge types include:
- `extends` — Profile inheritance
- `contains` — Profile contains an attribute definition
- `uses_validation` — Attribute definition uses a validation mechanism
- `assigned_to` — FDO type assigned to a profile

## Visualization

Generate a visual graph of the type system:

```bash
cd typesystem
pip install networkx graphviz
python visualize.py
```

This produces `typesystem_graph.png` showing:
- **Profiles** as blue nodes
- **Attribute definitions** as green nodes
- **Validation mechanisms** as orange nodes
- **FDO types** as purple nodes
- **Syntax primitives** as gray nodes

### Customizing the visualization

Edit `visualize.py` to:
- Filter by edge type (e.g., show only `extends` relationships)
- Change node colors or shapes
- Output in different formats (SVG, PDF, DOT)

## Extending the Type System

To add new profiles or attribute definitions:

1. Add entries to the `profiles` or `attribute_definitions` sections in `typesystem.yaml`
2. Add corresponding edges to `graph_edges`
3. Re-run `visualize.py` to see the updated graph

## References

- [R1-1] through [R1-7]: PID system requirements
- [R3-1] through [R3-5]: FDO Record requirements
- [R4-1] through [R4-12]: Profile requirements
- [R5-1] through [R5-15]: Attribute definition requirements
- [R6-1] through [R6-6]: Syntax definition requirements
- [R7-1] through [R7-14]: Referencing mechanisms
- [R8-1] through [R8-5]: Validation requirements
- [R9-1] through [R9-2]: Mandatory and optional attributes
- [R10-1] through [R10-15]: FDO types and operations
- [R11-1] through [R11-6]: Updating and evolution