"""
SharedContext Merger — Safe merging of tool memory_updates.

Responsible for:
  - Merging tool memory_updates into SharedContext safely
  - Preserving existing values if updates are None
  - Handling append-only operations (chunks, executed tools)
  - Supporting future multi-tool workflows

Design principle: Updates only overwrite if explicitly provided (not None).
"""

from __future__ import annotations

import logging
from typing import Optional

from app.shared_context.models import SharedContext, MemoryUpdate

logger = logging.getLogger(__name__)


def merge_shared_context(
    context: SharedContext,
    update: MemoryUpdate,
) -> SharedContext:
    """
    Safely merge a MemoryUpdate into SharedContext.

    Rules:
      - Only overwrites existing values if update provides non-None value
      - Preserves existing values if update field is None
      - Append operations (chunks, tools) use list concatenation
      - Returns new SharedContext (original unchanged)

    Args:
        context: Original SharedContext
        update: MemoryUpdate from tool

    Returns:
        New SharedContext with updates merged
    """

    # Create copy to avoid mutation
    merged = context.copy()

    # ========================================================================
    # Scalar fields — overwrite if update is not None
    # ========================================================================

    if update.origin_station is not None:
        merged.origin_station = update.origin_station
        logger.debug(f"Merged: origin_station → {update.origin_station}")

    if update.destination_station is not None:
        merged.destination_station = update.destination_station
        logger.debug(f"Merged: destination_station → {update.destination_station}")

    if update.travel_date is not None:
        merged.travel_date = update.travel_date
        logger.debug(f"Merged: travel_date → {update.travel_date}")

    if update.travel_day is not None:
        merged.travel_day = update.travel_day
        logger.debug(f"Merged: travel_day → {update.travel_day}")

    if update.train_class is not None:
        merged.train_class = update.train_class
        logger.debug(f"Merged: train_class → {update.train_class}")

    if update.quota is not None:
        merged.quota = update.quota
        logger.debug(f"Merged: quota → {update.quota}")

    if update.pnr_number is not None:
        merged.pnr_number = update.pnr_number
        logger.debug(f"Merged: pnr_number → {update.pnr_number}")

    if update.train_number is not None:
        merged.train_number = update.train_number
        logger.debug(f"Merged: train_number → {update.train_number}")

    if update.policy_topic is not None:
        merged.policy_topic = update.policy_topic
        logger.debug(f"Merged: policy_topic → {update.policy_topic}")

    if update.latest_user_pnr is not None:
        merged.latest_user_pnr = update.latest_user_pnr
        logger.debug(f"Merged: latest_user_pnr → {update.latest_user_pnr}")

    if update.inferred_train_number is not None:
        merged.inferred_train_number = update.inferred_train_number
        logger.debug(f"Merged: inferred_train_number → {update.inferred_train_number}")

    if update.waitlist_detected is not None:
        merged.waitlist_detected = update.waitlist_detected
        logger.debug(f"Merged: waitlist_detected → {update.waitlist_detected}")

    if update.alternate_route_required is not None:
        merged.alternate_route_required = update.alternate_route_required
        logger.debug(f"Merged: alternate_route_required → {update.alternate_route_required}")

    # ========================================================================
    # Append operations — concatenate lists
    # ========================================================================

    if update.append_chunks:
        merged.retrieved_knowledge_chunks.extend(update.append_chunks)
        logger.debug(f"Merged: appended {len(update.append_chunks)} knowledge chunks")

    if update.append_executed_tool:
        if update.append_executed_tool not in merged.executed_tools:
            merged.executed_tools.append(update.append_executed_tool)
            logger.debug(f"Merged: appended executed_tool → {update.append_executed_tool}")

    if update.append_failed_tool:
        if update.append_failed_tool not in merged.failed_tools:
            merged.failed_tools.append(update.append_failed_tool)
            logger.debug(f"Merged: appended failed_tool → {update.append_failed_tool}")

    return merged
