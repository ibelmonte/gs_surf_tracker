"""
Service for merging multiple surfer identities into a single surfer.

Handles the logic for combining events, pictures, and cleaning up
filesystem after surfer identification.
"""
from typing import List, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime
import logging
import shutil

logger = logging.getLogger(__name__)


class SurferMergeService:
    """Service for merging surfer identities."""

    @staticmethod
    def validate_surfer_ids(
        results_json: Dict[str, Any],
        surfer_ids: List[int]
    ) -> Tuple[bool, str]:
        """
        Validate that surfer IDs exist in results_json.

        Args:
            results_json: The session results JSON
            surfer_ids: List of surfer IDs to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not results_json or 'surfers' not in results_json:
            return False, "Session has no results"

        existing_ids = {s['id'] for s in results_json['surfers']}
        invalid_ids = [sid for sid in surfer_ids if sid not in existing_ids]

        if invalid_ids:
            return False, f"Invalid surfer IDs: {invalid_ids}"

        # Check for duplicates in request
        if len(surfer_ids) != len(set(surfer_ids)):
            return False, "Duplicate surfer IDs provided"

        return True, ""

    @staticmethod
    def merge_surfers(
        results_json: Dict[str, Any],
        surfer_ids: List[int]
    ) -> Dict[str, Any]:
        """
        Merge selected surfers into a single surfer identity.

        Args:
            results_json: The session results JSON
            surfer_ids: List of surfer IDs to merge

        Returns:
            Updated results_json with merged surfer
        """
        surfers = results_json['surfers']

        # Separate selected and unselected surfers
        selected_surfers = [s for s in surfers if s['id'] in surfer_ids]
        unselected_surfers = [s for s in surfers if s['id'] not in surfer_ids]

        # Use lowest ID as the merged ID
        merged_id = min(surfer_ids)

        # Collect all events and pictures from selected surfers
        all_events = []
        all_pictures = []

        for surfer in selected_surfers:
            all_events.extend(surfer.get('events', []))
            all_pictures.extend(surfer.get('pictures', []))

        # Sort events chronologically (timestamp primary, frame secondary)
        all_events.sort(key=lambda e: (e.get('timestamp', 0), e.get('frame', 0)))

        # Create merged surfer object
        merged_surfer = {
            'id': merged_id,
            'total_maneuvers': len(all_events),
            'events': all_events,
            'pictures': all_pictures,
            'merged_from': sorted(surfer_ids),
            'merged_at': datetime.utcnow().isoformat() + 'Z'
        }

        # Build new results_json
        # Only include the merged surfer - unselected surfers are deleted
        new_results = {
            'surfers': [merged_surfer],
            'merged': True,
            'original_surfer_count': len(surfers)
        }

        # Preserve other fields from original results
        for key in results_json:
            if key not in ['surfers', 'merged', 'original_surfer_count']:
                new_results[key] = results_json[key]

        return new_results

    @staticmethod
    def delete_unselected_surfer_files(
        output_path: str,
        surfer_ids: List[int],
        all_surfer_ids: List[int]
    ) -> List[int]:
        """
        Delete filesystem directories for unselected surfers.

        Args:
            output_path: Base output directory path
            surfer_ids: List of surfer IDs to keep
            all_surfer_ids: List of all surfer IDs in session

        Returns:
            List of surfer IDs that were successfully deleted
        """
        deleted_ids = []
        output_dir = Path(output_path)

        if not output_dir.exists():
            logger.warning(f"Output directory does not exist: {output_path}")
            return deleted_ids

        elements_dir = output_dir / "elements"
        if not elements_dir.exists():
            logger.warning(f"Elements directory does not exist: {elements_dir}")
            return deleted_ids

        # Delete directories for unselected surfers
        for surfer_id in all_surfer_ids:
            if surfer_id not in surfer_ids:
                surfer_dir = elements_dir / str(surfer_id)

                if surfer_dir.exists():
                    try:
                        shutil.rmtree(surfer_dir)
                        deleted_ids.append(surfer_id)
                        logger.info(f"Deleted surfer directory: {surfer_dir}")
                    except Exception as e:
                        logger.error(f"Failed to delete surfer directory {surfer_dir}: {e}")
                        # Continue even if deletion fails

        return deleted_ids

    @staticmethod
    def get_merge_statistics(
        original_results: Dict[str, Any],
        merged_results: Dict[str, Any],
        deleted_surfer_ids: List[int]
    ) -> Dict[str, Any]:
        """
        Calculate statistics about the merge operation.

        Args:
            original_results: Original results_json
            merged_results: New results_json after merge
            deleted_surfer_ids: IDs of surfers that were deleted

        Returns:
            Dictionary with merge statistics
        """
        merged_surfer = merged_results['surfers'][0]

        return {
            'merged_surfer_id': merged_surfer['id'],
            'total_events_merged': merged_surfer['total_maneuvers'],
            'surfers_removed': len(deleted_surfer_ids),
            'message': f"Successfully merged {len(merged_surfer.get('merged_from', []))} surfers"
        }
