from django import template
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
    
    # Simple hash function to consistently map label name to color
    hash_value = hash(str(label_name).lower()) % len(colors)
    return colors[hash_value]


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
    
    # Simple hash function to consistently map label name to color
    hash_value = hash(str(label_name).lower()) % len(colors)
    return colors[hash_value]
