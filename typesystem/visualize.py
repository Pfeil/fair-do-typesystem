#!/usr/bin/env python3
"""
FDO Type System Visualization
=============================

Generates a graph visualization of the FDO type system from the YAML
reconstruction file. Uses networkx for graph construction and graphviz
for layout and rendering.

Usage:
    pip install pyyaml networkx graphviz
    python visualize.py [--format png|svg|pdf|dot] [--filter-edge EXTENDS|CONTAINS|USES_VALIDATION|ASSIGNED_TO]
    python visualize.py --help

Output:
    typesystem_graph.<ext> in the same directory as this script.
"""

import argparse
import os
import sys

import networkx as nx
import yaml
from graphviz import Digraph

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
YAML_PATH = os.path.join(SCRIPT_DIR, "typesystem.yaml")

NODE_COLORS = {
    "profile": "#4A90D9",  # blue
    "attribute_definition": "#50C878",  # green
    "validation_mechanism": "#F5A623",  # orange
    "fdo_type": "#9B59B6",  # purple
    "syntax_primitive": "#95A5A6",  # gray
    "inferred_syntax": "#BDC3C7",  # light gray
}

NODE_SHAPES = {
    "profile": "box3d",
    "attribute_definition": "box",
    "validation_mechanism": "ellipse",
    "fdo_type": "diamond",
    "syntax_primitive": "circle",
    "inferred_syntax": "circle",
}

EDGE_COLORS = {
    "extends": "#2C3E50",
    "contains": "#7F8C8D",
    "uses_validation": "#E74C3C",
    "assigned_to": "#8E44AD",
}

EDGE_STYLES = {
    "extends": "bold",
    "contains": "solid",
    "uses_validation": "dashed",
    "assigned_to": "dotted",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_yaml(path: str) -> dict:
    """Load and return the typesystem YAML file."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_graph(data: dict, edge_filter: str | None = None) -> nx.DiGraph:
    """
    Build a NetworkX directed graph from the YAML data.

    Nodes are added from profiles, attribute_definitions,
    validation_mechanisms, fdo_types, syntax_primitives, and
    inferred_syntax_definitions. Edges come from the graph_edges
    section, optionally filtered by type.
    """
    G = nx.DiGraph()

    # --- Profiles ---
    for p in data.get("profiles", []):
        G.add_node(p["id"], label=p["id"], node_type="profile")

    # --- Attribute definitions ---
    for a in data.get("attribute_definitions", []):
        G.add_node(a["pid"], label=a["pid"], node_type="attribute_definition")

    # --- Validation mechanisms ---
    for v in data.get("validation_mechanisms", []):
        G.add_node(v["name"], label=v["name"], node_type="validation_mechanism")

    # --- FDO types ---
    for t in data.get("fdo_types", []):
        G.add_node(t["name"], label=t["name"], node_type="fdo_type")

    # --- Syntax primitives ---
    for s in data.get("syntax_primitives", []):
        G.add_node(s["name"], label=s["name"], node_type="syntax_primitive")

    # --- Inferred syntax definitions ---
    for s in data.get("inferred_syntax_definitions", []):
        G.add_node(s["pid"], label=s["pid"], node_type="inferred_syntax")

    # --- Edges ---
    for e in data.get("graph_edges", []):
        if edge_filter is not None and e["type"] != edge_filter:
            continue
        G.add_edge(e["from"], e["to"], edge_type=e["type"])

    return G


def to_graphviz(G: nx.DiGraph, output_format: str = "png") -> str:
    """
    Render the NetworkX graph using Graphviz and return the output path.

    Nodes are colored and shaped by their node_type. Edges are styled
    by their edge_type.
    """
    dot = Digraph(
        comment="FDO Type System",
        format=output_format,
        engine="dot",
    )
    dot.attr(rankdir="TB", size="12,16", fontsize="10")

    # Node defaults
    dot.attr("node", fontsize="10", fontname="Helvetica")

    # Add nodes
    for node, attrs in G.nodes(data=True):
        ntype = attrs.get("node_type", "attribute_definition")
        color = NODE_COLORS.get(ntype, "#FFFFFF")
        shape = NODE_SHAPES.get(ntype, "box")
        dot.node(
            node,
            label=attrs.get("label", node),
            style="filled",
            fillcolor=color,
            shape=shape,
            penwidth="2",
        )

    # Add edges
    for src, dst, attrs in G.edges(data=True):
        etype = attrs.get("edge_type", "contains")
        color = EDGE_COLORS.get(etype, "#000000")
        style = EDGE_STYLES.get(etype, "solid")
        label_map = {
            "extends": "extends",
            "contains": "",
            "uses_validation": "validates",
            "assigned_to": "type",
        }
        dot.edge(
            src,
            dst,
            color=color,
            style=style,
            label=label_map.get(etype, ""),
            fontsize="8",
        )

    # Render
    out_path = os.path.join(SCRIPT_DIR, f"typesystem_graph.{output_format}")
    dot.render(out_path, cleanup=True)
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Visualize the FDO type system as a graph."
    )
    parser.add_argument(
        "--format",
        choices=["png", "svg", "pdf", "dot"],
        default="png",
        help="Output format (default: png)",
    )
    parser.add_argument(
        "--filter-edge",
        choices=["extends", "contains", "uses_validation", "assigned_to"],
        default=None,
        help="Show only edges of this type",
    )
    parser.add_argument(
        "--yaml",
        default=YAML_PATH,
        help="Path to the typesystem YAML file",
    )
    args = parser.parse_args()

    # Load data
    try:
        data = load_yaml(args.yaml)
    except FileNotFoundError:
        print(f"Error: YAML file not found at {args.yaml}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as exc:
        print(f"Error parsing YAML: {exc}", file=sys.stderr)
        sys.exit(1)

    # Build graph
    G = build_graph(data, edge_filter=args.filter_edge)

    if G.number_of_nodes() == 0:
        print(
            "Warning: No nodes in the graph. Check your YAML or filter.",
            file=sys.stderr,
        )

    # Render
    out = to_graphviz(G, output_format=args.format)
    print(f"Graph saved to {out}")


if __name__ == "__main__":
    main()
