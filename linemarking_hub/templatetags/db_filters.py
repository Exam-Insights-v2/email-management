from django import template
from django.utils import timezone
from django.utils.dateformat import format
from datetime import datetime
import builtins

register = template.Library()


@register.filter
def getattr_filter(obj, attr):
    """Get attribute from object using Python's built-in getattr"""
    try:
        # Use builtins.getattr to avoid recursion
        value = builtins.getattr(obj, attr, None)
        
        # If it's a callable (method), don't call it
        if callable(value) and not isinstance(value, type):
            return None
            
        # If it's a property or descriptor, try to get its value
        if hasattr(type(obj), attr):
            attr_obj = builtins.getattr(type(obj), attr, None)
            if hasattr(attr_obj, '__get__'):
                try:
                    return attr_obj.__get__(obj, type(obj))
                except Exception:
                    pass
        
        return value
    except (AttributeError, TypeError, Exception):
        return None


@register.filter
def replace(value, arg):
    """Replace occurrences of a substring in a string
    
    Usage: {{ value|replace:"old|new" }}
    Note: Django template filters can only take one argument, so we use a pipe-separated format
    """
    if not value:
        return value
    
    try:
        # Parse the argument which should be in format "old|new"
        if '|' in arg:
            old, new = arg.split('|', 1)
            return str(value).replace(old, new)
        else:
            # If no pipe, just return the value
            return value
    except Exception:
        return value


@register.filter
def slice_filter(value, arg):
    """Slice a list or string using pipe-separated format
    
    Usage: {{ value|slice_filter:"|8" }} for [:8] or {{ value|slice_filter:"0|50" }} for [0:50] or {{ value|slice_filter:"5|" }} for [5:]
    Format: "start|end" where empty means None
    """
    if not value:
        return value
    
    try:
        # Parse the pipe-separated format (e.g., "|8", "0|50", "5|")
        if '|' in arg:
            parts = arg.split('|')
            start_str = parts[0].strip() if len(parts) > 0 and parts[0].strip() else None
            end_str = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
            
            start = int(start_str) if start_str else None
            end = int(end_str) if end_str else None
            
            # Apply slice
            if isinstance(value, str):
                return value[start:end]
            else:
                # For lists/querysets, convert to list first
                value_list = list(value) if hasattr(value, '__iter__') and not isinstance(value, str) else [value]
                return value_list[start:end]
        else:
            # If no pipe, try to use as single end index (like ":8")
            try:
                end = int(arg)
                if isinstance(value, str):
                    return value[:end]
                else:
                    value_list = list(value) if hasattr(value, '__iter__') and not isinstance(value, str) else [value]
                    return value_list[:end]
            except (ValueError, IndexError):
                return value
    except Exception:
        return value


def _deterministic_hash(text):
    """Create a deterministic hash from text that's consistent across Python restarts"""
    if not text:
        return 0
    # Simple deterministic hash function
    hash_value = 0
    for char in str(text).lower():
        hash_value = ((hash_value << 5) - hash_value) + ord(char)
        hash_value = hash_value & 0xFFFFFFFF  # Convert to 32-bit integer
    return abs(hash_value)


@register.filter
def label_color_bg(label_name):
    """Get consistent background/text color classes for a label based on its name"""
    if not label_name:
        return 'bg-gray-400/10 text-gray-600'
    
    # Color options for background and text
    colors = [
        'bg-red-400/10 text-red-600',
        'bg-blue-400/10 text-blue-600',
        'bg-yellow-400/10 text-yellow-600',
        'bg-green-400/10 text-green-600',
        'bg-purple-400/10 text-purple-600',
        'bg-pink-400/10 text-pink-600',
        'bg-indigo-400/10 text-indigo-600',
        'bg-orange-400/10 text-orange-600',
    ]
    
    # Use deterministic hash function to consistently map label name to color
    hash_value = _deterministic_hash(str(label_name).lower())
    return colors[hash_value % len(colors)]


@register.filter
def aus_time(value, format_string=None):
    """
    Convert datetime to Australia/Sydney timezone and format it.
    
    Usage: {{ task.created_at|aus_time:"d M Y H:i" }}
    Default format: "d M Y H:i" if not specified
    """
    if not value:
        return ""
    
    try:
        # Use Django's timezone utilities (no pytz needed)
        # Django's timezone.localtime() converts to the TIME_ZONE setting (Australia/Sydney)
        if timezone.is_aware(value):
            # Convert to local timezone (Australia/Sydney from settings)
            aus_time_value = timezone.localtime(value)
        else:
            # Make it timezone-aware using UTC, then convert to local
            aware_value = timezone.make_aware(value, timezone.utc)
            aus_time_value = timezone.localtime(aware_value)
        
        # Format the time using Django's dateformat
        # Map common format codes
        format_map = {
            'd': '%d',  # Day of month, 2 digits
            'M': '%b',  # Short month name
            'Y': '%Y',  # 4-digit year
            'H': '%H',  # 24-hour format hour
            'i': '%M',  # Minutes
            'g': '%I',  # 12-hour format hour (without leading zero)
            'a': '%p',  # AM/PM
        }
        
        if format_string:
            # Convert Django format to strftime format
            strftime_format = format_string
            for django_code, strftime_code in format_map.items():
                strftime_format = strftime_format.replace(django_code, strftime_code)
            formatted = aus_time_value.strftime(strftime_format)
            # Capitalize month names (replace lowercase month abbreviations with capitalized versions)
            month_map = {
                'jan': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'apr': 'Apr',
                'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'aug': 'Aug',
                'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dec': 'Dec'
            }
            for lower, upper in month_map.items():
                formatted = formatted.replace(lower, upper)
            return formatted
        else:
            formatted = aus_time_value.strftime("%d %b %Y %H:%M")
            # Capitalize month
            month_map = {
                'jan': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'apr': 'Apr',
                'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'aug': 'Aug',
                'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dec': 'Dec'
            }
            for lower, upper in month_map.items():
                formatted = formatted.replace(lower, upper)
            return formatted
    except (AttributeError, TypeError, ValueError) as e:
        # Fallback to regular date formatting if conversion fails
        try:
            if format_string:
                return value.strftime(format_string) if hasattr(value, 'strftime') else str(value)
            return str(value)
        except:
            return str(value)


@register.filter
def label_color_dot(label_name):
    """Get consistent dot color class for a label based on its name"""
    if not label_name:
        return 'bg-gray-400'
    
    # Color options for dot
    colors = [
        'bg-red-400',
        'bg-blue-400',
        'bg-yellow-400',
        'bg-green-400',
        'bg-purple-400',
        'bg-pink-400',
        'bg-indigo-400',
        'bg-orange-400',
    ]
    
    # Use deterministic hash function to consistently map label name to color
    hash_value = _deterministic_hash(str(label_name).lower())
    return colors[hash_value % len(colors)]


@register.filter
def priority_word(priority):
    """Convert priority number (1-5) to word"""
    if not priority:
        return "Lowest"
    
    try:
        priority_int = int(priority)
        priority_map = {
            1: "Lowest",
            2: "Low",
            3: "Medium",
            4: "High",
            5: "Urgent"
        }
        return priority_map.get(priority_int, f"Priority {priority_int}")
    except (ValueError, TypeError):
        return str(priority)


@register.filter
def priority_color(priority):
    """Returns Tailwind CSS color classes for priority badge based on priority level."""
    if not priority:
        return "bg-gray-400/10 text-gray-400"
    
    try:
        priority_int = int(priority)
        color_map = {
            1: "bg-gray-400/10 text-gray-400",  # Lowest - gray
            2: "bg-blue-400/10 text-blue-400",  # Low - blue
            3: "bg-amber-400/10 text-amber-400",  # Medium - amber/yellow
            4: "bg-orange-400/10 text-orange-400",  # High - orange
            5: "bg-red-400/10 text-red-400",  # Urgent - red
        }
        return color_map.get(priority_int, "bg-gray-400/10 text-gray-400")
    except (ValueError, TypeError):
        return "bg-gray-400/10 text-gray-400"


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using a key"""
    if not dictionary or not isinstance(dictionary, dict):
        return None
    return dictionary.get(key, [])
