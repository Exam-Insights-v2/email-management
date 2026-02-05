# MCP Action System Implementation Plan

## Overview
Replace rigid sequential action execution with an MCP-based system that allows the AI to dynamically decide which actions to run, in what order, based on email context and Standard Operating Procedures (SOPs).

## Goals
- ✅ Dynamic, context-aware action execution
- ✅ Support for Standard Operating Procedures
- ✅ Keep it simple - minimal changes to existing structure
- ✅ Backward compatible with existing labels/actions
- ✅ Allow AI to interpret email content and make decisions

---

## Phase 1: Foundation (Simple Start)

### 1.1 Add SOP Support to Models

**Add to `automation/models.py`:**
```python
class StandardOperatingProcedure(models.Model):
    """SOPs that guide AI decision-making for actions"""
    account = models.ForeignKey(
        "accounts.Account", on_delete=models.CASCADE, related_name="sops"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(help_text="When this SOP applies")
    instructions = models.TextField(help_text="What the AI should do when this SOP applies")
    priority = models.PositiveIntegerField(default=1, help_text="Higher priority SOPs are considered first")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority", "name"]
    
    def __str__(self):
        return self.name
```

**Enhance `Action` model:**
- Add `mcp_tool_name` field (optional) - if set, action is exposed as MCP tool
- Keep `function` for backward compatibility
- Add `tool_description` field - description for MCP tool

**Enhance `Label` model:**
- Add `sop_context` field (optional) - additional SOP context specific to this label

### 1.2 Install MCP Dependencies

Add to `requirements.txt`:
```
mcp
```

### 1.3 Create MCP Action Executor

**New file: `automation/mcp_executor.py`**
- Simple MCP server that exposes actions as tools
- Takes email context + available actions + SOPs
- Returns AI decision on which actions to run and in what order

---

## Phase 2: MCP Integration

### 2.1 MCP Tool Registry

**Create `automation/mcp_tools.py`:**
- Registry of available action tools
- Each action becomes an MCP tool with:
  - Tool name (from `action.mcp_tool_name` or `action.function`)
  - Description (from `action.tool_description` or `action.instructions`)
  - Parameters (email context, action instructions)
  - Execution function

### 2.2 Action Execution Functions

**Enhance `automation/tasks.py`:**
- Keep existing `run_draft_action` for backward compatibility
- Add new `execute_mcp_action` function that:
  - Takes action + email + context
  - Executes the action based on its function type
  - Returns result for AI to use in next decisions

**Action Types to Support:**
1. `draft_reply` - Create draft email reply
2. `create_task` - Create task in system
3. `notify` - Send notification
4. `schedule` - Schedule follow-up
5. `forward` - Forward email
6. `archive` - Archive email
7. (Extensible for future actions)

### 2.3 MCP Action Orchestrator

**New file: `automation/mcp_orchestrator.py`:**
- Main function: `orchestrate_label_actions(label, email, client)`
- Builds context:
  - Email content (subject, body, from, etc.)
  - Available actions for this label
  - Relevant SOPs (from account + label)
  - Account settings (writing style, signature)
- Calls AI with MCP tools available
- AI decides which actions to run and in what order
- Executes actions dynamically
- Returns execution results

---

## Phase 3: AI Prompt Engineering

### 3.1 Context Builder

**New file: `automation/context_builder.py`:**
- `build_action_context(label, email, account)` function
- Gathers:
  - Email details
  - Label prompt + SOP context
  - Account SOPs (active, ordered by priority)
  - Available actions (as MCP tool descriptions)
  - Account writing style
  - Previous actions/results (if any)

### 3.2 AI Prompt Template

**System prompt structure:**
```
You are an email action orchestrator for a line-marking company in Australia.

STANDARD OPERATING PROCEDURES:
{account_sops}
{label_sop_context}

AVAILABLE ACTIONS (MCP Tools):
{available_actions_list}

EMAIL CONTEXT:
Subject: {email.subject}
From: {email.from_address}
Body: {email.body_html}

ACCOUNT SETTINGS:
Writing Style: {account.writing_style}

INSTRUCTIONS:
1. Analyse the email content
2. Review relevant SOPs
3. Decide which actions to execute and in what order
4. Use MCP tools to execute actions
5. Adapt based on email context - skip unnecessary actions, change order if needed
6. Use Australian English spelling

Return your action plan and execute using the available MCP tools.
```

---

## Phase 4: Migration Strategy

### 4.1 Backward Compatibility

- Keep `LabelAction.order` field (for reference/UI)
- Add `use_mcp` boolean flag to `Label` model (default: False)
- If `use_mcp=False`, use old sequential execution
- If `use_mcp=True`, use new MCP orchestration
- Allows gradual migration

### 4.2 Update `trigger_label_actions` Task

**Modify `automation/tasks.py`:**
```python
@shared_task
def trigger_label_actions(label_id: int, email_message_id: int):
    label = Label.objects.get(pk=label_id)
    email = EmailMessage.objects.select_related("account").get(pk=email_message_id)
    
    if label.use_mcp:
        # New MCP-based orchestration
        from automation.mcp_orchestrator import orchestrate_label_actions
        client = OpenAIClient()
        orchestrate_label_actions(label, email, client)
    else:
        # Old sequential execution (backward compatible)
        # ... existing code ...
```

---

## Phase 5: UI Enhancements (Optional)

### 5.1 SOP Management
- Add SOP CRUD in admin/UI
- Link SOPs to accounts
- Show SOPs in label detail view

### 5.2 Action Configuration
- Add `mcp_tool_name` and `tool_description` fields to action form
- Show which actions are MCP-enabled
- Toggle `use_mcp` flag per label

### 5.3 Execution Logging
- Log AI decisions (which actions chosen, why)
- Show execution results
- Debug view for action orchestration

---

## Implementation Steps (Priority Order)

### Step 1: Foundation (Week 1)
1. ✅ Add `StandardOperatingProcedure` model + migration
2. ✅ Add `mcp_tool_name`, `tool_description` to `Action` model
3. ✅ Add `sop_context` to `Label` model
4. ✅ Add `use_mcp` flag to `Label` model
5. ✅ Install MCP dependency

### Step 2: MCP Tools (Week 1-2)
1. ✅ Create `automation/mcp_tools.py` - tool registry
2. ✅ Create action execution functions for each action type
3. ✅ Test individual action execution

### Step 3: Orchestrator (Week 2)
1. ✅ Create `automation/mcp_orchestrator.py`
2. ✅ Create `automation/context_builder.py`
3. ✅ Implement AI prompt with SOPs
4. ✅ Integrate MCP tool calling

### Step 4: Integration (Week 2-3)
1. ✅ Update `trigger_label_actions` to support both modes
2. ✅ Test with existing labels (backward compatible)
3. ✅ Test with MCP-enabled labels
4. ✅ Add error handling and logging

### Step 5: Polish (Week 3)
1. ✅ Add execution logging
2. ✅ UI for SOP management (if needed)
3. ✅ Documentation
4. ✅ Migration guide for existing labels

---

## Example Usage

### Creating an SOP
```python
sop = StandardOperatingProcedure.objects.create(
    account=account,
    name="Urgent Customer Emails",
    description="Applies to emails marked urgent or from key customers",
    instructions="Always create task immediately, then draft reply within 2 hours. If after hours, notify manager.",
    priority=10
)
```

### Creating an MCP Action
```python
action = Action.objects.create(
    account=account,
    name="Create Urgent Task",
    function="create_task",
    mcp_tool_name="create_urgent_task",
    tool_description="Creates a high-priority task for urgent customer requests",
    instructions="Set priority to 5, due date to today"
)
```

### Label with MCP
```python
label = Label.objects.create(
    account=account,
    name="Urgent Customer Request",
    prompt="Customer emails marked urgent or from key accounts",
    sop_context="Check if after hours - if so, notify manager first",
    use_mcp=True
)

# Link actions (order is now just a suggestion/hint)
LabelAction.objects.create(label=label, action=action, order=1)
```

### How It Works
1. Email comes in → classified with label "Urgent Customer Request"
2. `trigger_label_actions` called → sees `use_mcp=True`
3. MCP orchestrator gathers:
   - Email context
   - Account SOPs (including "Urgent Customer Emails")
   - Label SOP context
   - Available actions
4. AI analyses and decides:
   - "It's after hours → notify manager first"
   - "Then create urgent task"
   - "Then draft reply"
5. Actions executed in AI-determined order
6. Results logged

---

## Benefits

1. **Dynamic Decision Making**: AI adapts to email content
2. **SOP Integration**: Business rules guide AI decisions
3. **Flexible Ordering**: No rigid sequence constraints
4. **Conditional Execution**: Skip unnecessary actions
5. **Extensible**: Easy to add new action types
6. **Backward Compatible**: Existing labels still work
7. **Simple**: Minimal changes to existing structure

---

## Future Enhancements (Post-MVP)

- Action result feedback loop (AI learns from outcomes)
- Multi-step action workflows
- Action dependencies and prerequisites
- Parallel action execution
- Action retry logic
- Custom action types via plugins
- Action execution history and analytics

---

## Questions to Consider

1. Should SOPs be account-level only, or also label-level?
   - **Recommendation**: Account-level with optional label-specific context
2. How detailed should action tool descriptions be?
   - **Recommendation**: Keep concise but include key parameters
3. Should we log all AI decisions for audit?
   - **Recommendation**: Yes, at least initially for debugging
4. What happens if AI decides to skip all actions?
   - **Recommendation**: Log it, but allow it (might be valid)

---

## Success Metrics

- ✅ Actions execute in contextually appropriate order
- ✅ SOPs influence AI decisions
- ✅ No breaking changes to existing functionality
- ✅ New actions can be added without code changes
- ✅ Execution time remains reasonable (< 10s per email)
