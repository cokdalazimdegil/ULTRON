"""
ULTRON Computer Awareness & Autonomous Task Engine (v14)
────────────────────────────────────────────────────────
Masaüstü görme, anlama, klavye/fare kontrolü, pencere/uygulama yönetimi ve otonom görev motoru.
"""

from computer.screen_capture import (
    capture_screen,
    capture_region,
    get_screen_resolution,
    get_monitors,
    get_virtual_screen_bounds,
    has_screen_changed,
    compute_image_dhash
)

from computer.computer_state import (
    ComputerState,
    current_computer_state,
    UIElement
)

from computer.window_manager import (
    get_active_window_info,
    list_visible_windows,
    find_window,
    focus_window,
    minimize_window,
    maximize_window,
    close_window
)

from computer.mouse_controller import (
    get_mouse_position,
    move_mouse,
    click,
    double_click,
    right_click,
    scroll,
    drag
)

from computer.keyboard_controller import (
    type_text,
    press_key,
    key_down,
    key_up,
    hotkey,
    paste_text
)

from computer.app_controller import (
    open_application,
    close_application,
    is_app_running,
    get_running_process_names
)

from computer.browser_controller import (
    browser_open,
    browser_search,
    browser_read_page,
    browser_new_tab,
    browser_back
)

from computer.screen_analyzer import (
    analyze_current_screen,
    detect_ui_bounding_boxes
)

from computer.safety_manager import (
    SafetyManager
)

from computer.research_engine import (
    execute_research_plan
)

from computer.task_executor import (
    TaskEngine,
    AutonomousTask,
    cancel_task,
    cancel_all_tasks,
    get_task,
    list_active_tasks
)

from computer.world_model import (
    world_model,
    UltronWorldModel,
    UncertaintyLevel,
)

from computer.screen_awareness import (
    screen_awareness,
    ScreenAwarenessEngine,
    ChangeSeverity,
    VisualScreenContext,
)


from computer.computer_controller import (
    computer_controller,
    HierarchicalComputerController,
    UIActionResult,
)

__all__ = [
    "capture_screen",
    "capture_region",
    "get_screen_resolution",
    "get_monitors",
    "get_virtual_screen_bounds",
    "has_screen_changed",
    "compute_image_dhash",
    "ComputerState",
    "current_computer_state",
    "UIElement",
    "get_active_window_info",
    "list_visible_windows",
    "find_window",
    "focus_window",
    "minimize_window",
    "maximize_window",
    "close_window",
    "get_mouse_position",
    "move_mouse",
    "click",
    "double_click",
    "right_click",
    "scroll",
    "drag",
    "type_text",
    "press_key",
    "key_down",
    "key_up",
    "hotkey",
    "paste_text",
    "open_application",
    "close_application",
    "is_app_running",
    "get_running_process_names",
    "browser_open",
    "browser_search",
    "browser_read_page",
    "browser_new_tab",
    "browser_back",
    "analyze_current_screen",
    "detect_ui_bounding_boxes",
    "screen_awareness",
    "ScreenAwarenessEngine",
    "ChangeSeverity",
    "world_model",
    "UltronWorldModel",
    "computer_controller",
    "HierarchicalComputerController",
    "UIActionResult",
    "SafetyManager",
    "execute_research_plan",
    "TaskEngine",
    "AutonomousTask",
    "cancel_task",
    "cancel_all_tasks",
    "get_task",
    "list_active_tasks",
    "proactive_watcher",
    "ProactiveWatcherEngine",
    "ProactiveAlert",
    "AlertCategory",
    "AlertSeverity",
]

from computer.proactive_watcher import (
    proactive_watcher,
    ProactiveWatcherEngine,
    ProactiveAlert,
    AlertCategory,
    AlertSeverity,
)



