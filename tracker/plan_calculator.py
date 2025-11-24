"""
Built-in plan calculator for generating planting care plans.
Works with data.json to calculate care schedules for plants.
"""
from datetime import date, timedelta
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


def calculate_plan(crop_name: str, planting_date: date, plant_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Calculate a care plan for a given crop based on planting date.
    
    Args:
        crop_name: Name of the crop (e.g., "Cucumbers")
        planting_date: Date when the crop was planted
        plant_data: Dictionary containing plant data from data.json (new flat structure)
        
    Returns:
        List of dictionaries with 'task' and 'due_date' keys
    """
    plan = []
    
    if not plant_data:
        logger.warning('calculate_plan: Invalid plant_data structure')
        return plan
    
    # Support both new structure (flat object with plant names as keys) and old structure (with 'plants' array)
    plant_info = None
    
    # Try new structure first: plant_data is a dict with plant names as keys (e.g., {"Basil": {...}, "Cucumbers": {...}})
    if isinstance(plant_data, dict):
        # Check exact match first
        if crop_name in plant_data:
            plant_info = plant_data[crop_name]
        # Try title case (e.g., "basil" -> "Basil")
        elif crop_name.title() in plant_data:
            plant_info = plant_data[crop_name.title()]
        # Try case-insensitive match
        else:
            crop_name_lower = crop_name.lower()
            for key, value in plant_data.items():
                if key.lower() == crop_name_lower:
                    plant_info = value
                    break
        
        # If not found and 'plants' key exists, try old structure
        if not plant_info and 'plants' in plant_data:
            for plant in plant_data['plants']:
                if plant.get('name', '').lower() == crop_name.lower():
                    plant_info = plant
                    break
    
    if not plant_info:
        logger.warning('calculate_plan: Plant "%s" not found in plant_data. Available plants: %s', 
                      crop_name, list(plant_data.keys())[:10] if isinstance(plant_data, dict) else 'N/A')
        return plan
    
    # Get care schedule
    care_schedule = plant_info.get('care_schedule', [])
    if not care_schedule:
        logger.warning('calculate_plan: No care_schedule found for "%s"', crop_name)
        return plan
    
    # Build plan with calculated dates
    for task_item in care_schedule:
        task_title = task_item.get('task_title', '')
        days_after = task_item.get('days_after_planting')
        
        # Skip tasks without days_after_planting (ongoing tasks are handled separately)
        if days_after is None or days_after == '':
            continue
        
        try:
            days = int(days_after)
            due_date = planting_date + timedelta(days=days)
            
            plan.append({
                'task': task_title,
                'due_date': due_date
            })
        except (ValueError, TypeError):
            logger.warning('calculate_plan: Invalid days_after_planting for task "%s"', task_title)
            continue
    
    # Sort by due_date
    plan.sort(key=lambda x: x.get('due_date', date.today()))
    
    logger.info('calculate_plan: Generated %d tasks for "%s"', len(plan), crop_name)
    return plan

