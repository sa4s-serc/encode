#!/usr/bin/env python3
"""
Extract features from Python code blocks for energy prediction
This matches the feature extraction used in training
"""

import ast
import math
import statistics
import json
import sys
from collections import Counter
from typing import Dict, List, Any, Tuple


class FeatureExtractor(ast.NodeVisitor):
    """Extract comprehensive features from AST nodes"""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset all counters"""
        self.node_counts = Counter()
        self.node_depths = []
        self.variable_names = []
        self.function_calls = []
        self.attribute_accesses = []
        self.literal_values = []
        self.operator_sequences = []
        self.control_flow_paths = []
        self.loop_nesting_depths = []
        self.conditional_nesting_depths = []
        self.branching_factors = []

        self.current_depth = 0
        self.max_depth_seen = 0
        self.parent_stack = []
        self.control_flow_stack = []
        self.loop_depth = 0
        self.conditional_depth = 0
        self.leaf_nodes = 0

        self.cyclomatic_complexity = 1
        self.cognitive_complexity = 0

        self.operators = set()
        self.operands = set()
        self.total_operators = 0
        self.total_operands = 0

    def extract_features(self, node: ast.AST) -> Dict[str, Any]:
        """Extract all features from an AST node"""
        self.reset()
        self.visit(node)

        # Calculate all metrics
        features = self._calculate_all_features()
        return features

    def generic_visit(self, node):
        """Track node information"""
        node_type = type(node).__name__

        self.node_counts[node_type] += 1
        self.node_depths.append(self.current_depth)

        self.max_depth_seen = max(self.max_depth_seen, self.current_depth)

        children = list(ast.iter_child_nodes(node))
        self.branching_factors.append(len(children))

        if len(children) == 0:
            self.leaf_nodes += 1

        self.parent_stack.append(node)
        self.current_depth += 1

        super().generic_visit(node)

        self.current_depth -= 1
        self.parent_stack.pop()

    def visit_Name(self, node):
        """Track variables"""
        self.variable_names.append(node.id)
        self.operands.add(node.id)
        self.total_operands += 1
        self.generic_visit(node)

    def visit_Call(self, node):
        """Track function calls"""
        if isinstance(node.func, ast.Name):
            self.function_calls.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            if hasattr(node.func, 'attr'):
                self.function_calls.append(f"method:{node.func.attr}")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        """Track attribute access"""
        if hasattr(node, 'attr'):
            self.attribute_accesses.append(node.attr)
        self.generic_visit(node)

    def visit_Constant(self, node):
        """Track literals (Python 3.8+)"""
        self.literal_values.append(str(node.value))
        self.operands.add(str(node.value))
        self.total_operands += 1
        self.generic_visit(node)

    def visit_Num(self, node):
        """Track numeric literals (pre-3.8)"""
        self.literal_values.append(str(node.n))
        self.operands.add(str(node.n))
        self.total_operands += 1
        self.generic_visit(node)

    def visit_Str(self, node):
        """Track string literals (pre-3.8)"""
        self.literal_values.append(str(node.s))
        self.operands.add(node.s)
        self.total_operands += 1
        self.generic_visit(node)

    def visit_BinOp(self, node):
        """Track binary operators"""
        op_name = type(node.op).__name__
        self.operator_sequences.append(op_name)
        self.operators.add(op_name)
        self.total_operators += 1
        self.generic_visit(node)

    def visit_Compare(self, node):
        """Track comparison operators"""
        for op in node.ops:
            op_name = type(op).__name__
            self.operator_sequences.append(op_name)
            self.operators.add(op_name)
            self.total_operators += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        """Track boolean operators"""
        op_name = type(node.op).__name__
        self.operator_sequences.append(op_name)
        self.operators.add(op_name)
        self.total_operators += 1
        self.generic_visit(node)

    def visit_If(self, node):
        """Track if statements"""
        self.cyclomatic_complexity += 1
        self.cognitive_complexity += 1 + self.conditional_depth

        self.conditional_depth += 1
        self.conditional_nesting_depths.append(self.conditional_depth)

        self.control_flow_stack.append('If')
        path = "->".join(self.control_flow_stack)
        self.control_flow_paths.append(path)

        self.generic_visit(node)

        self.conditional_depth -= 1
        self.control_flow_stack.pop()

    def visit_For(self, node):
        """Track for loops"""
        self.cyclomatic_complexity += 1
        self.cognitive_complexity += 1 + self.loop_depth

        self.loop_depth += 1
        self.loop_nesting_depths.append(self.loop_depth)

        self.control_flow_stack.append('For')
        path = "->".join(self.control_flow_stack)
        self.control_flow_paths.append(path)

        self.generic_visit(node)

        self.loop_depth -= 1
        self.control_flow_stack.pop()

    def visit_While(self, node):
        """Track while loops"""
        self.cyclomatic_complexity += 1
        self.cognitive_complexity += 1 + self.loop_depth

        self.loop_depth += 1
        self.loop_nesting_depths.append(self.loop_depth)

        self.control_flow_stack.append('While')
        path = "->".join(self.control_flow_stack)
        self.control_flow_paths.append(path)

        self.generic_visit(node)

        self.loop_depth -= 1
        self.control_flow_stack.pop()

    def visit_Try(self, node):
        """Track try blocks"""
        self.cyclomatic_complexity += 1
        self.cognitive_complexity += 1

        self.control_flow_stack.append('Try')
        path = "->".join(self.control_flow_stack)
        self.control_flow_paths.append(path)

        self.generic_visit(node)
        self.control_flow_stack.pop()

    def _calculate_entropy(self, counter: Counter) -> float:
        """Calculate Shannon entropy"""
        if not counter:
            return 0.0

        total = sum(counter.values())
        entropy = 0.0

        for count in counter.values():
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)

        return entropy

    def _calculate_all_features(self) -> Dict[str, Any]:
        """Calculate all processed features"""

        # Basic metrics
        total_nodes = len(self.node_depths)
        unique_node_types = len(self.node_counts)
        max_depth = self.max_depth_seen
        avg_depth = statistics.mean(self.node_depths) if self.node_depths else 0
        depth_variance = statistics.variance(self.node_depths) if len(self.node_depths) > 1 else 0

        # Density metrics
        operator_density = len(self.operator_sequences) / max(1, total_nodes)
        literal_density = len(self.literal_values) / max(1, total_nodes)
        call_density = len(self.function_calls) / max(1, total_nodes)
        variable_density = len(self.variable_names) / max(1, total_nodes)
        attribute_density = len(self.attribute_accesses) / max(1, total_nodes)

        # Diversity metrics
        node_type_entropy = self._calculate_entropy(self.node_counts)
        operator_entropy = self._calculate_entropy(Counter(self.operator_sequences))
        variable_entropy = self._calculate_entropy(Counter(self.variable_names))

        unique_variables = len(set(self.variable_names))
        unique_operators = len(set(self.operator_sequences))
        unique_functions = len(set(self.function_calls))

        # Structural metrics
        avg_branching = statistics.mean(self.branching_factors) if self.branching_factors else 0
        max_branching = max(self.branching_factors) if self.branching_factors else 0
        leaves_ratio = self.leaf_nodes / max(1, total_nodes)

        # Pattern counts
        loops_count = self.node_counts.get('For', 0) + self.node_counts.get('While', 0)
        conditionals_count = self.node_counts.get('If', 0)
        functions_count = self.node_counts.get('FunctionDef', 0)
        classes_count = self.node_counts.get('ClassDef', 0)
        try_blocks_count = self.node_counts.get('Try', 0)

        # Nesting complexity
        max_loop_nesting = max(self.loop_nesting_depths) if self.loop_nesting_depths else 0
        max_conditional_nesting = max(self.conditional_nesting_depths) if self.conditional_nesting_depths else 0
        nesting_complexity = max_loop_nesting + max_conditional_nesting

        control_flow_complexity = len(set(self.control_flow_paths))

        # Halstead metrics
        n1 = len(self.operators)
        n2 = len(self.operands)
        N1 = self.total_operators
        N2 = self.total_operands

        vocabulary_size = n1 + n2
        program_length = N1 + N2
        program_volume = program_length * (math.log2(vocabulary_size) if vocabulary_size > 0 else 0)
        program_difficulty = (n1 * N2) / (2 * n2) if n2 > 0 else 0
        program_effort = program_difficulty * program_volume

        # Return all features as a dictionary with "feature_" prefix to match training data
        return {
            'feature_total_nodes': total_nodes,
            'feature_unique_node_types': unique_node_types,
            'feature_max_depth': max_depth,
            'feature_avg_depth': avg_depth,
            'feature_depth_variance': depth_variance,
            'feature_cyclomatic_complexity': self.cyclomatic_complexity,
            'feature_cognitive_complexity': self.cognitive_complexity,
            'feature_nesting_complexity': nesting_complexity,
            'feature_control_flow_complexity': control_flow_complexity,
            'feature_operator_density': operator_density,
            'feature_literal_density': literal_density,
            'feature_call_density': call_density,
            'feature_variable_density': variable_density,
            'feature_attribute_density': attribute_density,
            'feature_node_type_entropy': node_type_entropy,
            'feature_operator_entropy': operator_entropy,
            'feature_variable_entropy': variable_entropy,
            'feature_unique_variables': unique_variables,
            'feature_unique_operators': unique_operators,
            'feature_unique_functions': unique_functions,
            'feature_avg_branching_factor': avg_branching,
            'feature_max_branching_factor': max_branching,
            'feature_leaves_to_nodes_ratio': leaves_ratio,
            'feature_loops_count': loops_count,
            'feature_conditionals_count': conditionals_count,
            'feature_functions_count': functions_count,
            'feature_classes_count': classes_count,
            'feature_try_blocks_count': try_blocks_count,
            'feature_vocabulary_size': vocabulary_size,
            'feature_program_length': program_length,
            'feature_program_volume': program_volume,
            'feature_program_difficulty': program_difficulty,
            'feature_program_effort': program_effort
        }


def extract_code_blocks(code: str) -> List[Dict[str, Any]]:
    """Extract all code blocks from Python code"""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {'error': f'Syntax error: {e}'}

    blocks = []
    extractor = FeatureExtractor()

    def process_node(node: ast.AST, parent=None, level=0):
        """Recursively process AST nodes"""
        # Only process nodes with body (code blocks)
        if hasattr(node, 'body') and hasattr(node, 'lineno'):
            block_type = type(node).__name__

            # Only track specific block types
            if block_type in ['FunctionDef', 'For', 'While', 'If', 'Try', 'With']:
                start_line = node.lineno
                end_line = getattr(node, 'end_lineno', None)

                if not end_line and hasattr(node, 'body') and node.body:
                    last_node = node.body[-1]
                    end_line = getattr(last_node, 'end_lineno', start_line)

                if not end_line:
                    end_line = start_line

                # Extract features for this block
                features = extractor.extract_features(node)

                block_info = {
                    'block_type': block_type,
                    'start_line': start_line,
                    'end_line': end_line,
                    'features': features
                }

                blocks.append(block_info)

        # Process children
        for child in ast.iter_child_nodes(node):
            process_node(child, parent=node, level=level+1)

    process_node(tree)

    return blocks


def main():
    """Main entry point for feature extraction"""
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'No input provided'}))
        sys.exit(1)

    # Read code from stdin or file
    if sys.argv[1] == '--stdin':
        code = sys.stdin.read()
    else:
        with open(sys.argv[1], 'r') as f:
            code = f.read()

    # Extract blocks and features
    blocks = extract_code_blocks(code)

    # Output as JSON
    print(json.dumps(blocks, indent=2))


if __name__ == '__main__':
    main()
