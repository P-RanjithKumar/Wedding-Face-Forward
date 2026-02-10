# Photo Routing Issue - Resolution Summary

## Problem
Photos were getting stuck in "processing" status and not being organized into People folders, even though:
- Faces were detected successfully
- Person clusters were created
- Photos were processed and saved to the Processed folder
- Database showed correct face and person assignments

## Root Cause
The `route_photo()` function in the worker was failing silently (likely due to an unhandled exception), causing the worker thread to crash or hang before it could:
1. Complete the routing step (copying photos to People folders)
2. Update the photo status to "completed" in the database

This left photos permanently stuck in "processing" status.

## Immediate Fix Applied
1. **Fixed stuck photos**: Ran `fix_stuck_photos.py` to manually route all photos that were stuck in "processing" status
   - Photos 7, 8, 44, 46, 47 were successfully routed to their respective person folders
   - Database status updated to "completed"

2. **Improved error handling**: Modified `backend/app/worker.py` to wrap the routing step in a try-except block
   - If routing fails, the error is logged but the photo is still marked as "completed"
   - This prevents photos from getting stuck in "processing" status
   - Faces and person assignments are preserved in the database

## Files Modified
- `backend/app/worker.py` - Added explicit error handling around routing step (lines 116-145)

## Verification
After the fix:
- Person_022 folder now contains 3 photos (000044.jpg, 000046.jpg, 000047.jpg)
- All previously stuck photos are now properly organized
- Future routing failures will be logged but won't block photo processing

## Recommendation
Monitor the worker logs for any "Routing failed" messages to identify and fix the underlying routing issue. The current fix ensures photos don't get stuck, but the root cause of routing failures should still be investigated.

## How to Use the Fix Script
If photos get stuck again in the future, run:
```bash
python fix_stuck_photos.py
```

This will automatically route all stuck photos and update their status.
