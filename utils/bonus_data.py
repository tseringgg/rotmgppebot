"""
Utility functions for loading and managing bonus data.
"""
import csv
from dataclass import Bonus
from typing import Dict

def load_bonuses() -> Dict[str, Bonus]:
    """
    Load bonuses from the CSV file and return a dictionary mapping bonus names to Bonus objects.
    
    Returns:
        dict: Dictionary where keys are bonus names and values are Bonus objects
    """
    bonuses = {}
    
    try:
        with open('bonuses.csv', 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                bonus_name = row['Bonus Name'].strip()
                points = float(row['Points'])
                repeatable = row['Repeatable'].strip().lower() == 'true'
                
                bonuses[bonus_name] = Bonus(
                    name=bonus_name,
                    points=points,
                    repeatable=repeatable
                )
    except FileNotFoundError:
        print("Warning: bonuses.csv file not found")
    except Exception as e:
        print(f"Error loading bonuses: {e}")
    
    return bonuses

def get_bonus_names() -> list[str]:
    """
    Get a list of all available bonus names.
    
    Returns:
        list: List of bonus names
    """
    bonuses = load_bonuses()
    return list(bonuses.keys())