# -*- coding: utf-8 -*-
"""
DIAGNOSTIC: Elevation Marker Direction Vector Analysis
Small test to investigate 45° orientation issue by examining direction properties.
"""

__title__ = "Diagnostic\nMarker Direction"
__doc__ = "Analyze elevation marker direction vectors to solve 45° orientation issue."

# Standard pyRevit imports
from pyrevit import revit, DB, UI, script
import math

# Get current document
doc = revit.doc
uidoc = revit.uidoc

def analyze_elevation_marker_direction():
    """
    Diagnostic function to analyze elevation marker direction properties
    """
    print("=== ELEVATION MARKER DIRECTION DIAGNOSTIC ===")
    
    # Get one elevation marker for detailed analysis
    elevation_markers = list(DB.FilteredElementCollector(doc).OfClass(DB.ElevationMarker).ToElements())
    family_instances = DB.FilteredElementCollector(doc).OfClass(DB.FamilyInstance).ToElements()
    
    elevation_families = []
    for instance in family_instances:
        try:
            if instance.Symbol and instance.Symbol.Family:
                family_name = instance.Symbol.Family.Name.lower()
                if 'elevation' in family_name or 'marker' in family_name:
                    elevation_families.append(instance)
        except:
            continue
    
    print("Found {} ElevationMarker objects".format(len(elevation_markers)))
    print("Found {} FamilyInstance elevation markers".format(len(elevation_families)))
    
    # Analyze first FamilyInstance elevation marker
    if elevation_families:
        marker = elevation_families[0]
        print("\n--- FAMILYINSTANCE ELEVATION MARKER ANALYSIS ---")
        print("Marker ID: {}".format(marker.Id.Value))
        print("Family Name: {}".format(marker.Symbol.Family.Name))
        
        # Check location
        if marker.Location and hasattr(marker.Location, 'Point'):
            location = marker.Location.Point
            print("Location: ({:.2f}, {:.2f}, {:.2f})".format(location.X, location.Y, location.Z))
        
        # CRITICAL: Check FacingOrientation
        try:
            facing_orientation = marker.FacingOrientation
            print("FacingOrientation: ({:.4f}, {:.4f}, {:.4f})".format(
                facing_orientation.X, facing_orientation.Y, facing_orientation.Z))
            
            # Calculate angle from facing orientation
            angle_rad = math.atan2(facing_orientation.Y, facing_orientation.X)
            angle_deg = math.degrees(angle_rad)
            print("Facing Angle: {:.2f} degrees from X-axis".format(angle_deg))
            
        except Exception as e:
            print("ERROR getting FacingOrientation: {}".format(str(e)))
        
        # Check flip status
        try:
            facing_flipped = marker.FacingFlipped if hasattr(marker, 'FacingFlipped') else "N/A"
            hand_flipped = marker.HandFlipped if hasattr(marker, 'HandFlipped') else "N/A"
            print("FacingFlipped: {}, HandFlipped: {}".format(facing_flipped, hand_flipped))
        except Exception as e:
            print("ERROR getting flip status: {}".format(str(e)))
        
        # Check hand orientation
        try:
            hand_orientation = marker.HandOrientation if hasattr(marker, 'HandOrientation') else None
            if hand_orientation:
                print("HandOrientation: ({:.4f}, {:.4f}, {:.4f})".format(
                    hand_orientation.X, hand_orientation.Y, hand_orientation.Z))
                
                hand_angle_rad = math.atan2(hand_orientation.Y, hand_orientation.X)
                hand_angle_deg = math.degrees(hand_angle_rad)
                print("Hand Angle: {:.2f} degrees from X-axis".format(hand_angle_deg))
        except Exception as e:
            print("ERROR getting HandOrientation: {}".format(str(e)))
    
    # Analyze first ElevationMarker object
    if elevation_markers:
        marker = elevation_markers[0]
        print("\n--- ELEVATIONMARKER OBJECT ANALYSIS ---")
        print("Marker ID: {}".format(marker.Id.Value))
        print("Current View Count: {}".format(marker.CurrentViewCount))
        
        # Check location
        if marker.Location and hasattr(marker.Location, 'Point'):
            location = marker.Location.Point
            print("Location: ({:.2f}, {:.2f}, {:.2f})".format(location.X, location.Y, location.Z))
        
        # Analyze hosted elevation views
        for i in range(marker.CurrentViewCount):
            try:
                view_id = marker.GetViewId(i)
                if view_id and view_id != DB.ElementId.InvalidElementId:
                    elev_view = doc.GetElement(view_id)
                    if elev_view:
                        print("\n  Elevation View {}: {}".format(i, elev_view.Name))
                        
                        # CRITICAL: Check ViewDirection
                        try:
                            view_direction = elev_view.ViewDirection
                            print("  ViewDirection: ({:.4f}, {:.4f}, {:.4f})".format(
                                view_direction.X, view_direction.Y, view_direction.Z))
                            
                            # Calculate angle from view direction
                            view_angle_rad = math.atan2(view_direction.Y, view_direction.X)
                            view_angle_deg = math.degrees(view_angle_rad)
                            print("  View Angle: {:.2f} degrees from X-axis".format(view_angle_deg))
                            
                        except Exception as e:
                            print("  ERROR getting ViewDirection: {}".format(str(e)))
                        
                        # Check other view directions
                        try:
                            up_direction = elev_view.UpDirection
                            right_direction = elev_view.RightDirection
                            print("  UpDirection: ({:.4f}, {:.4f}, {:.4f})".format(
                                up_direction.X, up_direction.Y, up_direction.Z))
                            print("  RightDirection: ({:.4f}, {:.4f}, {:.4f})".format(
                                right_direction.X, right_direction.Y, right_direction.Z))
                        except Exception as e:
                            print("  ERROR getting view directions: {}".format(str(e)))
                            
            except Exception as e:
                print("  ERROR analyzing view {}: {}".format(i, str(e)))
    
    print("\n=== DIAGNOSTIC COMPLETE ===")
    print("Next step: Compare these angles with expected angles after 90° building rotation")
    print("If facing/view directions show 45° offset, we've found the root cause!")

def main():
    """Main diagnostic function"""
    try:
        with revit.Transaction("Elevation Marker Direction Diagnostic"):
            analyze_elevation_marker_direction()
        
        UI.TaskDialog.Show("Diagnostic Complete", 
                          "Elevation marker direction analysis complete!\n"
                          "Check the output for direction vector details.\n"
                          "Look for 45° offsets in facing/view angles.")
    except Exception as e:
        UI.TaskDialog.Show("Error", "Diagnostic failed: {}".format(str(e)))
        print("ERROR: {}".format(str(e)))

if __name__ == '__main__':
    main()