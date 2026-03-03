"""Horizontal step progress bar (1-10)."""

from dash import html

STEP_LABELS = [
    "Upload",
    "Compare",
    "Spot Check",
    "BTL Model",
    "Item Ruler",
    "Persons",
    "Discrim.",
    "Simulate",
    "Rasch",
    "Reports",
]


def make_step_indicator(current_step: int, completed_steps: list[int]) -> html.Div:
    """Return a horizontal step indicator component.

    Args:
        current_step: 1-based index of the active step.
        completed_steps: list of 1-based step numbers that are done.
    """
    children = []
    for i in range(1, 11):
        classes = ["step-circle"]
        if i == current_step:
            classes.append("active")
        if i in completed_steps:
            classes.append("completed")
        if i in completed_steps or i == current_step:
            classes.append("clickable")

        circle = html.Div(
            str(i),
            className=" ".join(classes),
            id={"type": "step-circle", "index": i},
            title=STEP_LABELS[i - 1],
        )

        wrapper = html.Div(
            [circle, html.Div(STEP_LABELS[i - 1], style={"fontSize": "0.65rem", "textAlign": "center", "marginTop": "2px"})],
            style={"display": "flex", "flexDirection": "column", "alignItems": "center", "minWidth": "50px"},
        )
        children.append(wrapper)

        if i < 10:
            connector_cls = "step-connector"
            if i in completed_steps:
                connector_cls += " completed"
            children.append(html.Div(className=connector_cls))

    return html.Div(children, className="step-indicator")
