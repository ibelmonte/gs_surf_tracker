"""
Service for calculating session scores based on activity and maneuver count.
"""
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ScoringService:
    """Service for calculating session performance scores."""

    @staticmethod
    def calculate_session_score(results_json: Dict[str, Any]) -> float:
        """
        Calculate score for a session based on duration and maneuver count.

        Score Formula: active_session_duration × total_maneuver_count

        Where:
        - active_session_duration: Time from first maneuver to last maneuver (seconds)
        - total_maneuver_count: Sum of all maneuvers across all surfers

        Args:
            results_json: The session results JSON containing surfer data

        Returns:
            Calculated score (float). Returns 0.0 if no maneuvers detected.
        """
        if not results_json or 'surfers' not in results_json:
            logger.warning("No surfers data in results_json")
            return 0.0

        surfers = results_json.get('surfers', [])
        if not surfers:
            logger.warning("No surfers found in results")
            return 0.0

        # Collect all events from all surfers
        all_events = []
        for surfer in surfers:
            events = surfer.get('events', [])
            all_events.extend(events)

        if not all_events:
            logger.info("No maneuvers detected in session")
            return 0.0

        # Calculate total maneuver count
        total_maneuvers = len(all_events)

        # Calculate active session duration (first to last maneuver)
        timestamps = [event.get('timestamp', 0) for event in all_events]
        timestamps.sort()

        first_timestamp = timestamps[0]
        last_timestamp = timestamps[-1]
        duration_seconds = last_timestamp - first_timestamp

        # Handle edge case: single maneuver (duration = 0)
        if duration_seconds == 0:
            # Use a minimum duration of 1 second for single-maneuver sessions
            duration_seconds = 1.0

        # Calculate score
        score = duration_seconds * total_maneuvers

        logger.info(
            f"Session score calculated: duration={duration_seconds:.2f}s, "
            f"maneuvers={total_maneuvers}, score={score:.2f}"
        )

        return round(score, 2)

    @staticmethod
    def get_session_statistics(results_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract session statistics for display/debugging.

        Args:
            results_json: The session results JSON

        Returns:
            Dictionary with session statistics
        """
        if not results_json or 'surfers' not in results_json:
            return {
                'total_surfers': 0,
                'total_maneuvers': 0,
                'duration_seconds': 0.0,
                'first_timestamp': None,
                'last_timestamp': None,
            }

        surfers = results_json.get('surfers', [])
        all_events = []

        for surfer in surfers:
            events = surfer.get('events', [])
            all_events.extend(events)

        if not all_events:
            return {
                'total_surfers': len(surfers),
                'total_maneuvers': 0,
                'duration_seconds': 0.0,
                'first_timestamp': None,
                'last_timestamp': None,
            }

        timestamps = [event.get('timestamp', 0) for event in all_events]
        timestamps.sort()

        first_timestamp = timestamps[0]
        last_timestamp = timestamps[-1]
        duration_seconds = last_timestamp - first_timestamp

        return {
            'total_surfers': len(surfers),
            'total_maneuvers': len(all_events),
            'duration_seconds': round(duration_seconds, 2),
            'first_timestamp': first_timestamp,
            'last_timestamp': last_timestamp,
        }
