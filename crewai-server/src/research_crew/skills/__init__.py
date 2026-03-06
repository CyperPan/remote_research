"""
Agent Skills Module - Specialized capabilities for each research agent

This module provides skill definitions and utilities for each agent type:
- Planner: Research & planning specialist with literature search capabilities
- Reviewer: Code quality & safety auditor with mathematical verification
- Coder: HPC Python & CUDA engineer with self-validation tools
- Executor: HPC cluster operations with NU Explorer specific knowledge
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional

def load_skill_content(skill_name: str) -> str:
    """Load skill file content for specified agent"""
    skill_file = Path(__file__) / f"{skill_name}_skill.md"
    if skill_file.exists():
        return skill_file.read_text()
    return f"Skill file for {skill_name} not found"

def get_agent_skills() -> Dict[str, Dict[str, Any]]:
    """Get skill configurations for all agents"""
    skills_dir = Path(__file__).parent
    
    return {
        "planner": {
            "description": "Research & Planning Specialist",
            "skill_file": skills_dir / "planner_skill.md",
            "tools": ["ArxivPaperTool", "BraveSearchTool"],
            "temperature": 0.8,
            "focus": "literature_review,research_design,resource_planning"
        },
        "reviewer": {
            "description": "Code Quality & Safety Auditor", 
            "skill_file": skills_dir / "reviewer_skill.md",
            "tools": ["CalculatorTool", "PyLintTool"],
            "temperature": 1.0,
            "focus": "code_review,math_verification,safety_audit"
        },
        "coder": {
            "description": "HPC Python & CUDA Engineer",
            "skill_file": skills_dir / "coder_skill.md", 
            "tools": ["PyLintTool"],
            "temperature": 0.15,
            "focus": "code_generation,hpc_optimization,self_validation"
        },
        "executor": {
            "description": "HPC Cluster Operations Specialist",
            "skill_file": skills_dir / "executor_skill.md",
            "tools": ["HPCSSHTool"],
            "temperature": 0.0,
            "focus": "cluster_access,job_management,execution_monitoring"
        }
    }

def get_skill_context(agent_name: str) -> str:
    """Get skill context for specific agent"""
    skills = get_agent_skills()
    if agent_name not in skills:
        return f"Unknown agent: {agent_name}"
    
    skill_info = skills[agent_name]
    skill_file = skill_info["skill_file"]
    
    if skill_file.exists():
        content = skill_file.read_text()
        # Extract key sections for context
        lines = content.split('\n')
        context_lines = []
        capture = False
        
        for line in lines:
            if line.startswith('## Core Capabilities'):
                capture = True
            elif line.startswith('## ') and capture:
                break
            elif capture:
                context_lines.append(line)
        
        return '\n'.join(context_lines)
    
    return f"Skill content not available for {agent_name}"

def validate_skills() -> Dict[str, bool]:
    """Validate that all skill files exist and are readable"""
    skills = get_agent_skills()
    validation_results = {}
    
    for agent_name, skill_info in skills.items():
        skill_file = skill_info["skill_file"]
        validation_results[agent_name] = skill_file.exists() and skill_file.is_file()
    
    return validation_results

# Skill-specific utilities
class SkillUtils:
    """Utility functions for agent skills"""
    
    @staticmethod
    def format_execution_summary(node: str, gpu_type: str, duration: str, 
                               exit_code: int, stdout: str, stderr: str) -> str:
        """Format execution summary for Executor agent"""
        status = "SUCCESS" if exit_code == 0 else "FAILED"
        
        return f"""
Execution Summary
=================
Node: {node}
GPU: {gpu_type}
Duration: {duration}
Exit Code: {exit_code}
Status: {status}

STDOUT:
{stdout[:1000]}{'...' if len(stdout) > 1000 else ''}

STDERR:
{stderr[:500]}{'...' if len(stderr) > 500 else ''}
""".strip()
    
    @staticmethod
    def format_review_status(approved: bool, issues: list, vram_analysis: dict) -> str:
        """Format review status for Reviewer agent"""
        status = "APPROVED" if approved else "NEEDS_REVISION"
        
        issues_text = "\n".join(f"{i+1}. {issue}" for i, issue in enumerate(issues))
        
        return f"""
[STATUS: {status}]

Issues Found:
{issues_text}

VRAM Analysis:
- Model Parameters: {vram_analysis.get('params_gb', 'N/A')} GB
- Optimizer State: {vram_analysis.get('optimizer_gb', 'N/A')} GB
- Activations: {vram_analysis.get('activations_gb', 'N/A')} GB
- Total Estimated: {vram_analysis.get('total_gb', 'N/A')} GB
""".strip()
    
    @staticmethod
    def format_research_plan(topic: str, objectives: list, methodology: str, 
                           resources: dict, timeline: str) -> str:
        """Format research plan for Planner agent"""
        objectives_text = "\n".join(f"{i+1}. {obj}" for i, obj in enumerate(objectives))
        
        return f"""
Research Plan for: {topic}
=============================

Objectives:
{objectives_text}

Methodology:
{methodology}

Resource Requirements:
- GPU Memory: {resources.get('gpu_memory', 'N/A')} GB
- CPU Cores: {resources.get('cpu_cores', 'N/A')}
- Memory: {resources.get('memory', 'N/A')} GB
- Time Estimate: {resources.get('time_estimate', 'N/A')} hours

Timeline: {timeline}
""".strip()

# Initialize skill validation
if __name__ == "__main__":
    validation = validate_skills()
    print("Skill validation results:")
    for agent, valid in validation.items():
        print(f"  {agent}: {'✓' if valid else '✗'}")
    
    if all(validation.values()):
        print("\nAll agent skills are properly configured!")
    else:
        print("\nSome agent skills are missing or invalid.")