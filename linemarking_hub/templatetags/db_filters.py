import re
from django import template
from django.utils import timezone
from django.utils.dateformat import format
from django.utils.safestring import mark_safe
from datetime import datetime
import builtins

register = template.Library()


def _strip_quoted_email_html(html):
    """Remove quoted/reply content from email HTML (blockquotes, Gmail quote divs, and 'On ... wrote:' sections).
    Also removes <style> and <script> tags to prevent them affecting the rest of the page.
    Removes dangerous inline styles that can break page layout."""
    if not html or not isinstance(html, str):
        return html
    text = html.strip()
    if not text:
        return html

    # Remove <style> tags and their content (these can't be scoped and affect the whole page)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove <script> tags and their content (security and isolation)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove dangerous inline styles that can break page layout
    # Match style="..." and remove problematic CSS properties
    def clean_style_attr(match):
        style_content = match.group(1)
        # Remove dangerous CSS properties that can break layout
        dangerous_props = [
            r'position\s*:\s*fixed',
            r'position\s*:\s*absolute',
            r'z-index\s*:\s*\d+',
            r'top\s*:\s*[^;]+',
            r'left\s*:\s*[^;]+',
            r'right\s*:\s*[^;]+',
            r'bottom\s*:\s*[^;]+',
            r'width\s*:\s*100%',
            r'height\s*:\s*100%',
            r'width\s*:\s*100vw',
            r'height\s*:\s*100vh',
        ]
        for prop in dangerous_props:
            style_content = re.sub(prop + r'[;\s]*', '', style_content, flags=re.IGNORECASE)
        # Clean up extra semicolons and spaces
        style_content = re.sub(r'[;\s]+', '; ', style_content).strip('; ')
        if style_content:
            return f'style="{style_content}"'
        return ''
    
    text = re.sub(r'style="([^"]*)"', clean_style_attr, text, flags=re.IGNORECASE)

    # Remove blockquote elements (repeat to handle nested; non-greedy gets innermost first)
    while True:
        match = re.search(
            r'<blockquote[^>]*>.*?</blockquote>',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if not match:
            break
        text = text[:match.start()] + text[match.end():]

    # Remove Gmail quote div: <div class="gmail_quote">...</div> (find matching closing tag by counting div depth)
    gmail_start = re.search(
        r'<div[^>]*class="[^"]*gmail_quote[^"]*"[^>]*>',
        text,
        re.IGNORECASE
    )
    if gmail_start:
        start = gmail_start.start()
        pos = gmail_start.end()
        depth = 1
        while pos < len(text) and depth > 0:
            next_open = text.find('<div', pos)
            next_close = text.find('</div>', pos)
            if next_close == -1:
                break
            if next_open != -1 and next_open < next_close:
                depth += 1
                pos = next_open + 4
            else:
                depth -= 1
                pos = next_close + 6
        if depth == 0:
            text = text[:start] + text[pos:].lstrip()

    # Remove Outlook/other "Original Message" or "On ... wrote:" blocks (often at end of body)
    # Match from "-----Original Message-----" or "On ... wrote:" to end (common reply boundaries)
    for pattern in (
        r'-----Original Message-----.*$',
        r'(?:<[^>]+>|\s)*On\s+.+?\s+wrote\s*:.*$',
        r'(?:<[^>]+>|\s)*From:\s*.+?Sent:\s*.+?To:\s*.+?Subject:.*$',
    ):
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)

    result = text.strip() or html
    return mark_safe(result)


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
            'a': '%p',  # am/pm
            'A': '%p',  # AM/PM (same as %p; we uppercase after)
        }
        
        if format_string:
            # Convert Django format to strftime format
            strftime_format = format_string
            for django_code, strftime_code in format_map.items():
                strftime_format = strftime_format.replace(django_code, strftime_code)
            formatted = aus_time_value.strftime(strftime_format)
            # 12-hour format: strip leading zero from hour (2:20pm not 02:20pm)
            if 'g' in format_string or 'a' in format_string or 'A' in format_string:
                import re
                formatted = re.sub(r' 0(\d)(?=:)', r' \1', formatted)
            # Capitalize month names (replace lowercase month abbreviations with capitalized versions)
            month_map = {
                'jan': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'apr': 'Apr',
                'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'aug': 'Aug',
                'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dec': 'Dec'
            }
            for lower, upper in month_map.items():
                formatted = formatted.replace(lower, upper)
            # If format had 'A', show AM/PM in capitals
            if 'A' in format_string:
                formatted = formatted.replace(' am', ' AM').replace(' pm', ' PM')
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


@register.filter(is_safe=True)
def strip_quoted_email(html):
    """Strip quoted/reply content from email body HTML so only the new message is shown."""
    return _strip_quoted_email_html(html)


@register.filter(is_safe=True)
def remove_global_style_script(html):
    """Remove <style> and <script> tags from HTML to prevent them affecting the rest of the page.
    Also removes dangerous inline styles that can break page layout.
    Keeps safe HTML and inline styles intact."""
    if not html or not isinstance(html, str):
        return html
    text = html.strip()
    if not text:
        return html
    
    # Remove <style> tags and their content (these can't be scoped and affect the whole page)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove <script> tags and their content (security and isolation)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove dangerous inline styles that can break page layout
    def clean_style_attr(match):
        style_content = match.group(1)
        # Remove dangerous CSS properties that can break layout
        dangerous_props = [
            r'position\s*:\s*fixed',
            r'position\s*:\s*absolute',
            r'z-index\s*:\s*\d+',
            r'top\s*:\s*[^;]+',
            r'left\s*:\s*[^;]+',
            r'right\s*:\s*[^;]+',
            r'bottom\s*:\s*[^;]+',
            r'width\s*:\s*100%',
            r'height\s*:\s*100%',
            r'width\s*:\s*100vw',
            r'height\s*:\s*100vh',
        ]
        for prop in dangerous_props:
            style_content = re.sub(prop + r'[;\s]*', '', style_content, flags=re.IGNORECASE)
        # Clean up extra semicolons and spaces
        style_content = re.sub(r'[;\s]+', '; ', style_content).strip('; ')
        if style_content:
            return f'style="{style_content}"'
        return ''
    
    text = re.sub(r'style="([^"]*)"', clean_style_attr, text, flags=re.IGNORECASE)
    
    result = text.strip() or html
    return mark_safe(result)


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using a key"""
    if not dictionary or not isinstance(dictionary, dict):
        return None
    return dictionary.get(key, [])


@register.filter
def attachment_icon(filename):
    """Return Tabler icon class for an attachment based on filename extension."""
    if not filename or not isinstance(filename, str):
        return "ti-file"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("jpg", "jpeg", "png", "gif", "webp", "svg", "bmp", "ico"):
        return "ti-photo"
    if ext in ("mp4", "webm", "mov", "avi", "mkv", "m4v"):
        return "ti-video"
    if ext in ("mp3", "wav", "ogg", "m4a", "flac", "aac"):
        return "ti-music"
    if ext == "pdf":
        return "ti-file-text"
    if ext in ("xls", "xlsx", "csv"):
        return "ti-file-spreadsheet"
    if ext in ("doc", "docx", "txt", "rtf"):
        return "ti-file-description"
    return "ti-file"


@register.filter
def attachment_icon_bg(filename):
    """Return Tailwind background colour classes for attachment icon box."""
    if not filename or not isinstance(filename, str):
        return "bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("jpg", "jpeg", "png", "gif", "webp", "svg", "bmp", "ico"):
        return "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-400"
    if ext in ("mp4", "webm", "mov", "avi", "mkv", "m4v"):
        return "bg-violet-100 dark:bg-violet-900/40 text-violet-600 dark:text-violet-400"
    if ext in ("mp3", "wav", "ogg", "m4a", "flac", "aac"):
        return "bg-amber-100 dark:bg-amber-900/40 text-amber-600 dark:text-amber-400"
    if ext == "pdf":
        return "bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400"
    if ext in ("xls", "xlsx", "csv"):
        return "bg-green-100 dark:bg-green-900/40 text-green-600 dark:text-green-400"
    if ext in ("doc", "docx", "txt", "rtf"):
        return "bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400"
    return "bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400"
