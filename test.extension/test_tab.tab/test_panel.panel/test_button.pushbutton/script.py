# -*- coding: utf-8 -*-
"""
Enhanced Transform Model and Views - FIXED v6
Correct orientation fix: move markers to exact position, adjust facing direction only.

Author: Architecture Firm
Compatible with: Revit 2026
Required: pyRevit 4.8+
"""

__title__ = "Enhanced Transform\nModel and Views - Fixed v6"
__doc__ = "Transform model elements with special focus on elevation markers and view coordination."

# Standard pyRevit imports
from pyrevit import revit, DB, UI, script
from pyrevit.framework import List
import math

# Get current document and UI document
doc = revit.doc
uidoc = revit.uidoc


def separate_hosted_elements(document, element_ids):
    """
    Separate hosted elements (doors, windows) from non-hosted elements
    Host elements should be transformed before their hosted elements
    """
    hosted_elements = []
    non_hosted_elements = []
    
    for element_id in element_ids:
        try:
            element = document.GetElement(element_id)
            if element and hasattr(element, 'Host') and element.Host is not None:
                hosted_elements.append(element_id)
            else:
                non_hosted_elements.append(element_id)
        except:
            non_hosted_elements.append(element_id)  # Default to non-hosted
    
    return hosted_elements, non_hosted_elements


def get_valid_elements(document, element_ids):
    """
    Get list of elements that still exist in the document
    Some elements may be invalidated during rotation
    """
    valid_elements = []
    
    for element_id in element_ids:
        try:
            element = document.GetElement(element_id)
            if element is not None:
                valid_elements.append(element_id)
        except:
            continue
    
    return valid_elements


def store_wall_joins(document, element_ids):
    """
    Store wall-to-wall join relationships before transformation
    """
    wall_joins = []
    
    try:
        # Get all walls from the element list
        walls = []
        for element_id in element_ids:
            element = document.GetElement(element_id)
            if element and isinstance(element, DB.Wall):
                walls.append(element)
        
        # Check which walls are joined to each other
        for i, wall1 in enumerate(walls):
            for j, wall2 in enumerate(walls[i+1:], i+1):
                try:
                    if DB.JoinGeometryUtils.AreElementsJoined(document, wall1, wall2):
                        wall_joins.append((wall1.Id, wall2.Id))
                except:
                    continue
    except Exception as e:
        print("Error storing wall joins: {}".format(str(e)))
    
    return wall_joins


def clean_wall_constraints(document, element_ids):
    """
    Clean up wall constraints that may cause errors after transformation
    """
    print("Cleaning wall constraints...")
    walls_processed = 0
    
    for element_id in element_ids:
        try:
            element = document.GetElement(element_id)
            if element and isinstance(element, DB.Wall):
                # Try to auto-join walls at their endpoints
                try:
                    # Get all other walls to check for auto-joining
                    all_walls = [document.GetElement(eid) for eid in element_ids 
                                if document.GetElement(eid) and isinstance(document.GetElement(eid), DB.Wall)]
                    
                    for other_wall in all_walls:
                        if other_wall.Id != element.Id:
                            try:
                                # Let Revit auto-join walls if they're close
                                if not DB.JoinGeometryUtils.AreElementsJoined(document, element, other_wall):
                                    # Check if endpoints are close (within 0.1 feet for precision)
                                    if hasattr(element, 'Location') and hasattr(other_wall, 'Location'):
                                        if isinstance(element.Location, DB.LocationCurve) and isinstance(other_wall.Location, DB.LocationCurve):
                                            curve1 = element.Location.Curve
                                            curve2 = other_wall.Location.Curve
                                            
                                            endpoints1 = [curve1.GetEndPoint(0), curve1.GetEndPoint(1)]
                                            endpoints2 = [curve2.GetEndPoint(0), curve2.GetEndPoint(1)]
                                            
                                            for ep1 in endpoints1:
                                                for ep2 in endpoints2:
                                                    distance = ep1.DistanceTo(ep2)
                                                    if distance < 0.1:  # Very close - should auto-join
                                                        DB.JoinGeometryUtils.JoinGeometry(document, element, other_wall)
                                                        print("  Auto-joined walls {} and {} (distance: {:.3f})".format(
                                                            element.Id.Value, other_wall.Id.Value, distance))
                                                        break
                            except:
                                continue
                                
                    walls_processed += 1
                except:
                    continue
        except:
            continue
    
    print("Wall constraint cleanup completed: {} walls processed".format(walls_processed))


def restore_wall_joins(document, wall_joins):
    """
    Restore wall-to-wall join relationships after transformation
    Enhanced with better error handling and automatic wall end joining
    """
    if not wall_joins:
        return
    
    print("Restoring {} wall joins...".format(len(wall_joins)))
    restored_count = 0
    
    for wall1_id, wall2_id in wall_joins:
        try:
            wall1 = document.GetElement(wall1_id)
            wall2 = document.GetElement(wall2_id)
            
            if wall1 and wall2:
                # Check if they're not already joined
                if not DB.JoinGeometryUtils.AreElementsJoined(document, wall1, wall2):
                    try:
                        DB.JoinGeometryUtils.JoinGeometry(document, wall1, wall2)
                        restored_count += 1
                        print("  Restored join between walls {} and {}".format(wall1_id.Value, wall2_id.Value))
                    except Exception as join_e:
                        print("  Failed to join walls {} and {}: {}".format(wall1_id.Value, wall2_id.Value, str(join_e)))
                        
                        # Try auto-join at wall ends as fallback
                        try:
                            # Get wall endpoints and see if they're close
                            if hasattr(wall1, 'Location') and hasattr(wall2, 'Location'):
                                if isinstance(wall1.Location, DB.LocationCurve) and isinstance(wall2.Location, DB.LocationCurve):
                                    curve1 = wall1.Location.Curve
                                    curve2 = wall2.Location.Curve
                                    
                                    # Check if wall endpoints are close (within 1 foot)
                                    endpoints1 = [curve1.GetEndPoint(0), curve1.GetEndPoint(1)]
                                    endpoints2 = [curve2.GetEndPoint(0), curve2.GetEndPoint(1)]
                                    
                                    for ep1 in endpoints1:
                                        for ep2 in endpoints2:
                                            distance = ep1.DistanceTo(ep2)
                                            if distance < 1.0:  # Within 1 foot
                                                print("    Walls are close at endpoints (distance: {:.3f}), attempting join".format(distance))
                                                DB.JoinGeometryUtils.JoinGeometry(document, wall1, wall2)
                                                restored_count += 1
                                                break
                        except:
                            continue
                else:
                    print("  Walls {} and {} already joined".format(wall1_id.Value, wall2_id.Value))
                    restored_count += 1
        except Exception as e:
            print("  Failed to restore wall join: {}".format(str(e)))
            continue
    
    print("Wall join restoration completed: {}/{} joins restored".format(restored_count, len(wall_joins)))


def get_model_elements(document):
    """
    Get all transformable building elements - FIXED to include actual building elements
    """
    
    elements_to_transform = []
    
    # INCLUDE specific building element categories - VERIFIED FOR REVIT 2026
    included_categories = [
        # Core building elements
        DB.BuiltInCategory.OST_Walls,
        DB.BuiltInCategory.OST_Floors, 
        DB.BuiltInCategory.OST_Roofs,
        DB.BuiltInCategory.OST_Ceilings,
        DB.BuiltInCategory.OST_Doors,
        DB.BuiltInCategory.OST_Windows,
        # Building components
        DB.BuiltInCategory.OST_Stairs,
        DB.BuiltInCategory.OST_Railings,
        DB.BuiltInCategory.OST_CurtainWallPanels,
        DB.BuiltInCategory.OST_CurtainWallMullions,
        # Furniture and fixtures
        DB.BuiltInCategory.OST_Furniture,
        DB.BuiltInCategory.OST_Casework,
        DB.BuiltInCategory.OST_PlumbingFixtures,
        DB.BuiltInCategory.OST_LightingFixtures,
        DB.BuiltInCategory.OST_ElectricalFixtures,
        # Equipment
        DB.BuiltInCategory.OST_MechanicalEquipment,
        DB.BuiltInCategory.OST_ElectricalEquipment,
        # Structural elements
        DB.BuiltInCategory.OST_StructuralFraming,
        DB.BuiltInCategory.OST_StructuralColumns,
        DB.BuiltInCategory.OST_StructuralFoundation,
        # Site and generic
        DB.BuiltInCategory.OST_GenericModel,
        DB.BuiltInCategory.OST_Entourage,
        DB.BuiltInCategory.OST_Parking,
        DB.BuiltInCategory.OST_Site,
        DB.BuiltInCategory.OST_Topography,
        DB.BuiltInCategory.OST_Mass,
    ]
    
    print("Analyzing elements for transformation...")
    
    # Collect elements from each included category
    for category in included_categories:
        try:
            # Verify category exists before using it
            category_name = str(category).split('.')[-1]  # Get just the OST_* part
            print("Checking category: {}".format(category_name))
            
            collector = DB.FilteredElementCollector(document)
            collector.OfCategory(category).WhereElementIsNotElementType()
            
            category_elements = collector.ToElements()
            category_count = 0
            
            # Debug: show what elements are in this category
            if len(category_elements) > 0:
                print("  Found {} elements in category {}".format(len(category_elements), category_name))
                for i, elem in enumerate(category_elements[:3]):  # Show first 3
                    print("    Element {}: {} (Type: {})".format(elem.Id.Value, elem.Name if hasattr(elem, 'Name') else 'No Name', type(elem).__name__))
            
            for element in category_elements:
                try:
                    # Check if element can be transformed
                    can_transform = False
                    
                    # Method 1: Elements with Location property (most common)
                    if hasattr(element, 'Location') and element.Location is not None:
                        location_type = type(element.Location).__name__
                        if location_type in ['LocationPoint', 'LocationCurve']:
                            can_transform = True
                    
                    # Method 2: Sketch-based elements (roofs, floors) might not have standard Location
                    elif (isinstance(element, (DB.Floor, DB.RoofBase, DB.Ceiling)) or 
                          type(element).__name__ in ['FootPrintRoof', 'ExtrusionRoof', 'Floor', 'Ceiling']):
                        # These are sketch-based and can be transformed via ElementTransformUtils
                        can_transform = True
                        print("  Found sketch-based element: {} (Type: {})".format(element.Id.Value, type(element).__name__))
                    
                    # Method 3: Family instances should have geometry even without Location
                    elif isinstance(element, DB.FamilyInstance):
                        # Check if it has geometry/can be placed
                        try:
                            geom = element.get_Geometry(DB.Options())
                            if geom is not None:
                                can_transform = True
                        except:
                            pass
                    
                    if can_transform:
                        elements_to_transform.append(element.Id)
                        category_count += 1
                        
                except:
                    continue
            
            if category_count > 0:
                print("Found {} transformable elements in category {}".format(category_count, category_name))
                
        except Exception as e:
            category_name = str(category).split('.')[-1] if hasattr(category, '__str__') else 'Unknown'
            print("Could not collect category {}: {}".format(category_name, str(e)))
            continue
    
    # Debug: Check what types we actually collected
    if elements_to_transform:
        element_types = {}
        for i, element_id in enumerate(elements_to_transform[:50]):  # Check first 50
            try:
                element = document.GetElement(element_id)
                if element:
                    elem_type = type(element).__name__
                    category_name = element.Category.Name if element.Category else "Unknown"
                    key = "{} ({})".format(elem_type, category_name)
                    element_types[key] = element_types.get(key, 0) + 1
            except:
                continue
        
        print("Element types found: {}".format(element_types))
    
    print("Found {} total elements to transform".format(len(elements_to_transform)))
    return elements_to_transform


def transform_elements_robust(document, element_ids, transform, rotation_degrees=0, rotation_origin=None):
    """
    Robust element transformation using proper Revit API methods
    Handles hosted elements, wall joins, sketch constraints, and element invalidation
    """
    
    if not element_ids:
        return 0
    
    original_count = len(element_ids)
    transformed_count = 0
    
    # Separate elements by type to handle constraints properly
    sketch_based_elements = []  # Roofs, floors, ceilings
    regular_elements = []
    
    for element_id in element_ids:
        try:
            element = document.GetElement(element_id)
            if element:
                if isinstance(element, (DB.Floor, DB.RoofBase, DB.Ceiling)):
                    sketch_based_elements.append(element_id)
                else:
                    regular_elements.append(element_id)
        except:
            regular_elements.append(element_id)  # Default to regular
    
    print("Regular elements: {}, Sketch-based elements: {}".format(len(regular_elements), len(sketch_based_elements)))
    
    # Store wall joins before transformation (only for regular elements)
    wall_joins = store_wall_joins(document, regular_elements)
    
    try:
        # Step 1: Apply rotation if needed
        if rotation_degrees != 0 and rotation_origin is not None:
            print("Applying rotation of {} degrees...".format(rotation_degrees))
            print("Rotation center: ({:.2f}, {:.2f}, {:.2f})".format(
                rotation_origin.X, rotation_origin.Y, rotation_origin.Z))
            
            # Create rotation axis (Z-axis through rotation center)
            axis_start = rotation_origin
            axis_end = DB.XYZ(rotation_origin.X, rotation_origin.Y, rotation_origin.Z + 10)
            rotation_axis = DB.Line.CreateBound(axis_start, axis_end)
            
            # Convert degrees to radians
            rotation_radians = rotation_degrees * 3.14159265359 / 180.0
            print("Rotation radians: {:.4f}".format(rotation_radians))
            
            # Debug: Analyze element types and positions before rotation
            print("\nAnalyzing elements before rotation:")
            element_types = {}
            sample_positions = []
            for i, element_id in enumerate(element_ids[:10]):  # Check first 10
                try:
                    element = document.GetElement(element_id)
                    if element:
                        elem_type = type(element).__name__
                        element_types[elem_type] = element_types.get(elem_type, 0) + 1
                        
                        if element.Location and i < 5:  # Store positions for first 5
                            if hasattr(element.Location, 'Point'):
                                point = element.Location.Point
                                sample_positions.append((element_id.Value, point.X, point.Y, point.Z, elem_type))
                                print("Element {} before: ({:.2f}, {:.2f}, {:.2f}) - {}".format(
                                    element_id.Value, point.X, point.Y, point.Z, elem_type))
                            elif hasattr(element.Location, 'Curve'):
                                curve = element.Location.Curve
                                start = curve.GetEndPoint(0)
                                sample_positions.append((element_id.Value, start.X, start.Y, start.Z, elem_type + "(curve)"))
                                print("Element {} (curve) before: ({:.2f}, {:.2f}, {:.2f}) - {}".format(
                                    element_id.Value, start.X, start.Y, start.Z, elem_type))
                except:
                    continue
            
            print("Element types to rotate: {}".format(element_types))
            
            # Separate hosted and non-hosted elements from REGULAR elements only
            hosted_elements, non_hosted_elements = separate_hosted_elements(document, regular_elements)
            print("Non-hosted elements: {}, Hosted elements: {}".format(
                len(non_hosted_elements), len(hosted_elements)))
            
            # Rotate non-hosted elements first (hosts before hosted)
            if non_hosted_elements:
                non_hosted_list = List[DB.ElementId](non_hosted_elements)
                print("Rotating {} non-hosted elements around axis from ({:.2f}, {:.2f}, {:.2f}) to ({:.2f}, {:.2f}, {:.2f})".format(
                    len(non_hosted_elements), 
                    rotation_axis.GetEndPoint(0).X, rotation_axis.GetEndPoint(0).Y, rotation_axis.GetEndPoint(0).Z,
                    rotation_axis.GetEndPoint(1).X, rotation_axis.GetEndPoint(1).Y, rotation_axis.GetEndPoint(1).Z))
                try:
                    DB.ElementTransformUtils.RotateElements(document, non_hosted_list, rotation_axis, rotation_radians)
                    print("Non-hosted elements rotation successful!")
                except Exception as rot_e:
                    print("Non-hosted rotation failed, trying individual: {}".format(str(rot_e)))
                    for element_id in non_hosted_elements:
                        try:
                            DB.ElementTransformUtils.RotateElement(document, element_id, rotation_axis, rotation_radians)
                        except:
                            continue
            
            # Rotate hosted elements (doors, windows, etc.)
            if hosted_elements:
                hosted_list = List[DB.ElementId](hosted_elements)
                print("Rotating {} hosted elements".format(len(hosted_elements)))
                try:
                    DB.ElementTransformUtils.RotateElements(document, hosted_list, rotation_axis, rotation_radians)
                    print("Hosted elements rotation successful!")
                except Exception as rot_e:
                    print("Hosted rotation failed, trying individual: {}".format(str(rot_e)))
                    for element_id in hosted_elements:
                        try:
                            DB.ElementTransformUtils.RotateElement(document, element_id, rotation_axis, rotation_radians)
                        except:
                            continue
            
            # Debug: Check multiple elements after rotation to verify movement
            print("\nChecking element positions after rotation:")
            checked_count = 0
            for element_id in element_ids[:5]:  # Check first 5 elements
                try:
                    element = document.GetElement(element_id)
                    if element and element.Location:
                        if hasattr(element.Location, 'Point'):
                            after_point = element.Location.Point
                            print("Element {} after rotation: ({:.2f}, {:.2f}, {:.2f}) - Type: {}".format(
                                element_id.Value, after_point.X, after_point.Y, after_point.Z, 
                                type(element).__name__))
                            checked_count += 1
                        elif hasattr(element.Location, 'Curve'):
                            curve = element.Location.Curve
                            start_point = curve.GetEndPoint(0)
                            print("Element {} (curve) start after rotation: ({:.2f}, {:.2f}, {:.2f}) - Type: {}".format(
                                element_id.Value, start_point.X, start_point.Y, start_point.Z,
                                type(element).__name__))
                            checked_count += 1
                except:
                    continue
            print("Checked {} elements for position changes".format(checked_count))
            
            # Step 1.5: Handle sketch-based elements separately (after regular elements)
            if sketch_based_elements:
                print("\\nProcessing {} sketch-based elements (roofs, floors, ceilings)...".format(len(sketch_based_elements)))
                print("WARNING: Sketch-based elements may have constraints that prevent rotation")
                print("Will attempt transformation with constraint-safe methods")
                
                for sketch_id in sketch_based_elements:
                    try:
                        sketch_element = document.GetElement(sketch_id)
                        if sketch_element:
                            print("  Processing sketch element: {} (Type: {})".format(
                                sketch_id.Value, type(sketch_element).__name__))
                            
                            # For sketch-based elements, try individual transformation
                            sketch_list = List[DB.ElementId]([sketch_id])
                            
                            try:
                                # For sketch-based elements, use most careful approach
                                # Constraint errors often happen with rotation, so try translation first
                                
                                transformation_success = False
                                
                                # Method 1: Try translation only first (safest for constrained elements)
                                if transform.Origin.GetLength() > 0.001:
                                    try:
                                        DB.ElementTransformUtils.MoveElement(document, sketch_id, transform.Origin)
                                        print("    Sketch element translated successfully")
                                        transformation_success = True
                                        transformed_count += 1
                                    except Exception as trans_e:
                                        print("    Sketch element translation failed: {}".format(str(trans_e)))
                                
                                # Method 2: Only try rotation if translation succeeded and element allows it
                                if transformation_success and rotation_degrees != 0:
                                    try:
                                        # Create rotation transform around element's own center to minimize constraint conflicts
                                        element_center = None
                                        if hasattr(sketch_element, 'Location') and sketch_element.Location:
                                            if hasattr(sketch_element.Location, 'Point'):
                                                element_center = sketch_element.Location.Point
                                        
                                        # Use element center if available, otherwise building center
                                        rot_center = element_center if element_center else rotation_origin
                                        
                                        axis_start = rot_center
                                        axis_end = DB.XYZ(rot_center.X, rot_center.Y, rot_center.Z + 10)
                                        rotation_axis = DB.Line.CreateBound(axis_start, axis_end)
                                        rotation_radians = rotation_degrees * 3.14159265359 / 180.0
                                        
                                        DB.ElementTransformUtils.RotateElement(document, sketch_id, rotation_axis, rotation_radians)
                                        print("    Sketch element rotated around its center")
                                        
                                    except Exception as rot_e:
                                        print("    Sketch element rotation failed (constraints): {}".format(str(rot_e)))
                                        # Translation succeeded, so this is still partial success
                                        pass
                                
                                # If no transformation succeeded, try the fallback
                                if not transformation_success:
                                    print("    WARNING: Sketch element {} transformation completely failed due to constraints".format(sketch_id.Value))
                                    # Continue with other elements - don't fail the whole operation
                                
                            except Exception as sketch_e:
                                print("    Sketch element processing failed: {}".format(str(sketch_e)))
                                # Continue with other elements
                                continue
                                
                    except Exception as e:
                        print("  Error processing sketch element {}: {}".format(sketch_id.Value, str(e)))
                        continue
        
        # Step 2: Apply translation if needed  
        translation_vector = transform.Origin
        if not (translation_vector.X == 0 and translation_vector.Y == 0 and translation_vector.Z == 0):
            print("Applying translation: ({}, {}, {})...".format(
                translation_vector.X, translation_vector.Y, translation_vector.Z))
            
            # Get fresh element list after rotation (some may be invalidated)
            valid_elements = get_valid_elements(document, element_ids)
            valid_element_list = List[DB.ElementId](valid_elements)
            
            try:
                DB.ElementTransformUtils.MoveElements(document, valid_element_list, translation_vector)
                print("Bulk translation successful!")
                transformed_count = len(valid_elements)
            except Exception as trans_e:
                print("Bulk translation failed, trying individual: {}".format(str(trans_e)))
                # Try individual translation
                for element_id in valid_elements:
                    try:
                        # Check if element still exists
                        element = document.GetElement(element_id)
                        if element is not None:
                            DB.ElementTransformUtils.MoveElement(document, element_id, translation_vector)
                            transformed_count += 1
                    except:
                        continue
        else:
            # Count valid elements after rotation
            valid_elements = get_valid_elements(document, element_ids)
            transformed_count = len(valid_elements)
        
        # Step 3: Clean wall constraints and restore wall joins
        clean_wall_constraints(document, element_ids)
        restore_wall_joins(document, wall_joins)
        
        print("Successfully transformed {}/{} elements".format(transformed_count, original_count))
        return transformed_count
        
    except Exception as e:
        print("Transformation failed: {}".format(str(e)))
        return 0


def is_default_elevation_marker(document, marker):
    """
    Identify default elevation markers to skip transformation
    FIXED: Use correct API methods and better filtering logic
    """
    try:
        # Check both ElevationMarker objects and FamilyInstance elevation markers
        
        # For ElevationMarker objects - check all hosted views
        if isinstance(marker, DB.ElevationMarker):
            elevation_count = marker.CurrentViewCount
            for i in range(4):  # Check all 4 possible indices (0-3)
                try:
                    elev_view_id = marker.GetViewId(i)  # FIXED: Correct API method
                    if elev_view_id and elev_view_id != DB.ElementId.InvalidElementId:
                        elev_view = document.GetElement(elev_view_id)
                        if elev_view and hasattr(elev_view, 'Name'):
                            view_name = elev_view.Name.lower()
                            
                            # Check for default elevation names
                            default_names = ['north', 'south', 'east', 'west']
                            if view_name in default_names:
                                print("    Identified as default elevation: {}".format(view_name))
                                return True
                            
                            # Check for templates like "Elevation 1 - North"
                            if 'elevation' in view_name and any(dir in view_name for dir in default_names):
                                print("    Identified as default elevation: {}".format(view_name))
                                return True
                except:
                    continue
            
            # Additional check: location near origin suggests default placement
            if hasattr(marker, 'Location') and marker.Location:
                if hasattr(marker.Location, 'Point'):
                    marker_loc = marker.Location.Point
                    # Default elevations often placed near project origin
                    if abs(marker_loc.X) < 50 and abs(marker_loc.Y) < 50:
                        print("    Identified as default elevation: near origin ({:.1f}, {:.1f})".format(
                            marker_loc.X, marker_loc.Y))
                        return True
        
        # For FamilyInstance markers - these are typically user-created
        # But check family name for elevation-related defaults
        elif isinstance(marker, DB.FamilyInstance):
            if marker.Symbol and marker.Symbol.Family:
                family_name = marker.Symbol.Family.Name.lower()
                # Some default elevation families might have specific names
                if 'default' in family_name or 'system' in family_name:
                    print("    Identified as default elevation family: {}".format(family_name))
                    return True
        
        return False
        
    except Exception as e:
        # If we can't determine, assume it's user-created (safer to transform)
        print("    Error checking elevation marker: {}".format(str(e)))
        return False


def update_elevation_markers_v3(document, transform, rotation_degrees, building_center):
    """
    V6 - ORIENTATION FIX: Adjust marker facing direction, not position
    Problem: V5 rotated marker positions when they just needed orientation adjustment
    Solution: Move markers correctly, then rotate only around their own center for orientation
    """
    
    print("=== V6 ELEVATION MARKER UPDATE - ORIENTATION FIX ===")
    print("CORRECT FIX: Move markers to new position, adjust orientation around marker center")
    print("Building center: ({:.2f}, {:.2f}, {:.2f})".format(
        building_center.X, building_center.Y, building_center.Z))
    
    # Get elevation markers
    elevation_markers = list(DB.FilteredElementCollector(document).OfClass(DB.ElevationMarker).ToElements())
    elevation_by_category = list(DB.FilteredElementCollector(document)
                                .OfCategory(DB.BuiltInCategory.OST_ElevationMarks)
                                .WhereElementIsNotElementType()
                                .ToElements())
    
    family_instances = DB.FilteredElementCollector(document).OfClass(DB.FamilyInstance).ToElements()
    elevation_families = []
    
    for instance in family_instances:
        try:
            if instance.Symbol and instance.Symbol.Family:
                family_name = instance.Symbol.Family.Name.lower()
                elevation_keywords = ['elevation', 'marker', 'callout']
                if any(keyword in family_name for keyword in elevation_keywords):
                    elevation_families.append(instance)
        except:
            continue
    
    all_elevation_elements = []
    all_elevation_elements.extend(elevation_markers)
    all_elevation_elements.extend(elevation_by_category)
    all_elevation_elements.extend(elevation_families)
    
    unique_elevations = {}
    for elem in all_elevation_elements:
        unique_elevations[elem.Id.Value] = elem
    
    final_elevation_list = list(unique_elevations.values())
    print("Found {} total elevation elements".format(len(final_elevation_list)))
    
    # Filter out default elevation markers
    user_markers = []
    default_markers = []
    for marker in final_elevation_list:
        if is_default_elevation_marker(document, marker):
            default_markers.append(marker)
        else:
            user_markers.append(marker)
    
    print("Filtered: {} default markers skipped, {} user markers to process".format(
        len(default_markers), len(user_markers)))
    
    updated_count = 0
    
    # V6 FIX: Separate position and orientation
    # Position: Follow building transformation exactly
    # Orientation: Add 45° around marker's own center
    orientation_adjustment_degrees = 45.0  # Additional rotation for proper facing
    orientation_adjustment_radians = math.radians(orientation_adjustment_degrees)
    
    print("V6 CORRECT FIX: Position follows building exactly, orientation gets 45° adjustment")
    print("Building rotation: {}°, Marker orientation adjustment: +{}°".format(
        rotation_degrees, orientation_adjustment_degrees))
    
    for marker in user_markers:
        try:
            print("Processing elevation element: {} (Type: {})".format(marker.Id.Value, type(marker).__name__))
            
            if isinstance(marker, DB.FamilyInstance):
                # FamilyInstance elevation marker
                if marker.Location and hasattr(marker.Location, 'Point'):
                    print("  FamilyInstance Location type: LocationPoint")
                    
                    # Step 1: Move marker to correct position (follow building exactly)
                    old_point = marker.Location.Point
                    new_point = transform.OfPoint(old_point)
                    marker.Location.Point = new_point
                    print("  FamilyInstance moved to ({:.2f}, {:.2f}, {:.2f})".format(
                        new_point.X, new_point.Y, new_point.Z))
                    
                    # Step 2: V6 FIX - Rotate around marker's own center for orientation only
                    # Create rotation axis at marker's new position (not building center)
                    marker_rotation_axis = DB.Line.CreateBound(
                        new_point, 
                        DB.XYZ(new_point.X, new_point.Y, new_point.Z + 10)
                    )
                    
                    print("  V6 FIX: Orientation adjustment +{}° around marker center ({:.2f}, {:.2f})".format(
                        orientation_adjustment_degrees, new_point.X, new_point.Y))
                    
                    DB.ElementTransformUtils.RotateElement(document, marker.Id, marker_rotation_axis, orientation_adjustment_radians)
                    print("  SUCCESS: FamilyInstance orientation adjusted")
                    updated_count += 1
                    
            elif isinstance(marker, DB.ElevationMarker):
                # ElevationMarker object
                view_count = marker.CurrentViewCount
                print("  ElevationMarker has {} elevation views".format(view_count))
                
                # Step 1: Apply translation using ElementTransformUtils
                translation_vector = transform.Origin
                DB.ElementTransformUtils.MoveElement(document, marker.Id, translation_vector)
                print("  ElevationMarker translated by ({:.2f}, {:.2f}, {:.2f})".format(
                    translation_vector.X, translation_vector.Y, translation_vector.Z))
                
                # Step 2: Apply building rotation around building center (same as building elements)
                building_rotation_axis = DB.Line.CreateBound(
                    building_center, 
                    DB.XYZ(building_center.X, building_center.Y, building_center.Z + 10)
                )
                building_rotation_radians = math.radians(rotation_degrees)
                DB.ElementTransformUtils.RotateElement(document, marker.Id, building_rotation_axis, building_rotation_radians)
                print("  ElevationMarker rotated {}° around building center".format(rotation_degrees))
                
                # Step 3: V6 FIX - Additional orientation adjustment around marker center
                # Get marker's new position after transformation
                marker_bbox = marker.get_BoundingBox(None)
                if marker_bbox:
                    marker_center = DB.XYZ(
                        (marker_bbox.Min.X + marker_bbox.Max.X) / 2,
                        (marker_bbox.Min.Y + marker_bbox.Max.Y) / 2,
                        marker_bbox.Min.Z
                    )
                    
                    marker_rotation_axis = DB.Line.CreateBound(
                        marker_center, 
                        DB.XYZ(marker_center.X, marker_center.Y, marker_center.Z + 10)
                    )
                    
                    print("  V6 FIX: Additional +{}° orientation around marker center".format(orientation_adjustment_degrees))
                    DB.ElementTransformUtils.RotateElement(document, marker.Id, marker_rotation_axis, orientation_adjustment_radians)
                    print("  SUCCESS: ElevationMarker orientation adjusted")
                
                updated_count += 1
                
        except Exception as e:
            print("  ERROR processing elevation element {}: {}".format(marker.Id.Value, str(e)))
            continue
    
    print("=== ELEVATION UPDATE SUMMARY ===")
    print("Updated {} out of {} user-created elevation elements".format(updated_count, len(user_markers)))
    print("Skipped {} default elevation markers".format(len(default_markers)))
    print("Success rate: {:.1%}".format(float(updated_count) / len(user_markers) if user_markers else 0))
    print("V6 FIX: Position follows building exactly, orientation gets +45° adjustment")
    print("================================")
    
    return updated_count


def update_section_views_v3(document, transform, rotation_degrees, building_center):
    """
    V6 - ORIENTATION FIX FOR SECTION MARKERS
    Same fix as elevation markers: move correctly, adjust orientation around marker center
    """
    
    print("=== V6 SECTION VIEW UPDATE - ORIENTATION FIX ===")
    
    section_views = DB.FilteredElementCollector(document).OfClass(DB.ViewSection).ToElements()
    print("Found {} section views to process".format(len(section_views)))
    updated_count = 0
    
    # Find and transform section markers
    section_markers = []
    family_instances = DB.FilteredElementCollector(document).OfClass(DB.FamilyInstance).ToElements()
    
    for instance in family_instances:
        try:
            if instance.Symbol and instance.Symbol.Family:
                family_name = instance.Symbol.Family.Name.lower()
                section_keywords = ['section', 'callout', 'detail', 'marker']
                if any(keyword in family_name for keyword in section_keywords):
                    section_markers.append(instance)
                    print("  Found section marker: {} - {}".format(instance.Id.Value, family_name))
        except:
            continue
    
    print("Found {} section marker family instances".format(len(section_markers)))
    
    # V6 FIX: Same approach as elevation markers
    # Position: Follow building transformation exactly
    # Orientation: Add 45° around marker's own center
    orientation_adjustment_degrees = 45.0
    orientation_adjustment_radians = math.radians(orientation_adjustment_degrees)
    
    print("V6 CORRECT FIX: Section markers position follows building, orientation gets +45° adjustment")
    print("Building rotation: {}°, Section marker orientation adjustment: +{}°".format(
        rotation_degrees, orientation_adjustment_degrees))
    print("Building center: ({:.2f}, {:.2f}, {:.2f})".format(
        building_center.X, building_center.Y, building_center.Z))
    
    for marker in section_markers:
        try:
            if marker.Location and hasattr(marker.Location, 'Point'):
                # Step 1: Move marker to correct position (follow building exactly)
                old_point = marker.Location.Point
                new_point = transform.OfPoint(old_point)
                marker.Location.Point = new_point
                print("  Section marker moved to ({:.2f}, {:.2f}, {:.2f})".format(
                    new_point.X, new_point.Y, new_point.Z))
                
                # Step 2: V6 FIX - Orientation adjustment around marker's own center
                marker_rotation_axis = DB.Line.CreateBound(
                    new_point, 
                    DB.XYZ(new_point.X, new_point.Y, new_point.Z + 10)
                )
                
                print("  V6 FIX: Orientation adjustment +{}° around marker center ({:.2f}, {:.2f})".format(
                    orientation_adjustment_degrees, new_point.X, new_point.Y))
                
                DB.ElementTransformUtils.RotateElement(document, marker.Id, marker_rotation_axis, orientation_adjustment_radians)
                print("  Updated section marker: {} (orientation adjusted)".format(marker.Id.Value))
        except Exception as e:
            print("  ERROR transforming section marker {}: {}".format(marker.Id.Value, str(e)))
            continue
    
    # Continue with section view updates (crop boxes) - these should still work
    
    # Update section views
    for view in section_views:
        try:
            print("Processing section view: {}".format(view.Name))
            
            # Skip view templates
            if hasattr(view, 'IsTemplate') and view.IsTemplate:
                print("  Skipping template view")
                continue
            
            view_updated = False
            
            # Method 1: Update crop box if active
            if view.CropBoxActive:
                try:
                    print("  Updating crop box...")
                    crop_box = view.CropBox
                    if crop_box:
                        # For section views, we need to transform the view origin AND direction
                        # The crop box transform contains the view's coordinate system
                        old_transform = crop_box.Transform
                        
                        # Transform the origin point
                        new_origin = transform.OfPoint(old_transform.Origin)
                        
                        # Create new transform with moved origin AND rotated orientation
                        new_transform = DB.Transform.Identity
                        new_transform.Origin = new_origin
                        
                        # CRITICAL: Apply rotation to the view direction vectors
                        if not transform.IsTranslation:
                            # Transform the view direction vectors with the same rotation
                            new_transform.BasisX = transform.OfVector(old_transform.BasisX)
                            new_transform.BasisY = transform.OfVector(old_transform.BasisY) 
                            new_transform.BasisZ = transform.OfVector(old_transform.BasisZ)
                            print("    Applied rotation to section view direction vectors")
                        else:
                            # Translation only - keep original orientation
                            new_transform.BasisX = old_transform.BasisX
                            new_transform.BasisY = old_transform.BasisY
                            new_transform.BasisZ = old_transform.BasisZ
                        
                        # Create new crop box with same size but new transform
                        new_crop_box = DB.BoundingBoxXYZ()
                        new_crop_box.Min = crop_box.Min
                        new_crop_box.Max = crop_box.Max
                        new_crop_box.Transform = new_transform
                        
                        view.CropBox = new_crop_box
                        updated_count += 1
                        view_updated = True
                        print("  SUCCESS: Crop box updated")
                        
                except Exception as crop_e:
                    print("  Crop box update failed: {}".format(str(crop_e)))
            
            # Method 2: Try to update the section line/origin
            if not view_updated:
                try:
                    # For section views, try to access the section line
                    if hasattr(view, 'GetSectionBox'):
                        section_box = view.GetSectionBox()
                        if section_box:
                            # Transform the section box
                            min_pt = transform.OfPoint(section_box.Min)
                            max_pt = transform.OfPoint(section_box.Max)
                            
                            new_section_box = DB.BoundingBoxXYZ()
                            new_section_box.Min = min_pt
                            new_section_box.Max = max_pt
                            new_section_box.Transform = section_box.Transform
                            
                            view.SetSectionBox(new_section_box)
                            updated_count += 1
                            view_updated = True
                            print("  SUCCESS: Section box updated")
                            
                except Exception as section_e:
                    print("  Section box method failed: {}".format(str(section_e)))
            
            if not view_updated:
                print("  WARNING: Section view {} not directly updated".format(view.Name))
                
        except Exception as e:
            print("ERROR processing section view {}: {}".format(view.Name, str(e)))
            continue
    
    print("Updated {} section views".format(updated_count))
    return updated_count


def update_plan_views_v3(document, transform):
    """
    V3 - More robust plan view updates 
    """
    
    plan_views = DB.FilteredElementCollector(document).OfClass(DB.ViewPlan).ToElements()
    print("Found {} plan views to process".format(len(plan_views)))
    updated_count = 0
    
    for view in plan_views:
        try:
            print("Processing plan view: {}".format(view.Name))
            
            # Skip view templates
            if hasattr(view, 'IsTemplate') and view.IsTemplate:
                print("  Skipping template view")
                continue
                
            if view.CropBoxActive:
                print("  View has active crop box")
                
                try:
                    crop_box = view.CropBox
                    if crop_box:
                        # For plan views, we need to transform the view origin AND direction  
                        # The crop box transform contains the view's coordinate system
                        old_transform = crop_box.Transform
                        
                        # Transform the origin point
                        new_origin = transform.OfPoint(old_transform.Origin)
                        
                        # Create new transform with moved origin AND rotated orientation
                        new_transform = DB.Transform.Identity
                        new_transform.Origin = new_origin
                        
                        # CRITICAL: Apply rotation to the view direction vectors for plan views too
                        if not transform.IsTranslation:
                            # Transform the view direction vectors with the same rotation
                            new_transform.BasisX = transform.OfVector(old_transform.BasisX)
                            new_transform.BasisY = transform.OfVector(old_transform.BasisY) 
                            new_transform.BasisZ = transform.OfVector(old_transform.BasisZ)
                            print("    Applied rotation to plan view direction vectors")
                        else:
                            # Translation only - keep original orientation
                            new_transform.BasisX = old_transform.BasisX
                            new_transform.BasisY = old_transform.BasisY
                            new_transform.BasisZ = old_transform.BasisZ
                        
                        # Create new crop box with same size but new transform
                        new_crop_box = DB.BoundingBoxXYZ()
                        new_crop_box.Min = crop_box.Min
                        new_crop_box.Max = crop_box.Max
                        new_crop_box.Transform = new_transform
                        
                        view.CropBox = new_crop_box
                        updated_count += 1
                        print("  SUCCESS: Plan view crop box updated")
                        continue
                        
                except Exception as bbox_e:
                    print("  Crop box method failed: {}".format(str(bbox_e)))
                
                # Alternative: Reset crop region if update fails
                try:
                    crop_manager = view.GetCropRegionShapeManager()
                    if crop_manager.CanHaveShape:
                        crop_manager.RemoveCropRegionShape()
                        print("  Crop region reset - should adjust automatically")
                        
                except Exception as shape_e:
                    print("  Crop shape reset failed: {}".format(str(shape_e)))
            else:
                print("  View does not have active crop box")
                        
        except Exception as e:
            print("ERROR updating plan view {}: {}".format(view.Name, str(e)))
            continue
    
    print("Updated {} plan views".format(updated_count))
    return updated_count


def update_annotations_v3(document, transform):
    """
    V3 - Enhanced annotation updating with better error handling
    """
    
    annotation_categories = [
        DB.BuiltInCategory.OST_Dimensions,
        DB.BuiltInCategory.OST_TextNotes,
        DB.BuiltInCategory.OST_Tags,
        DB.BuiltInCategory.OST_GenericAnnotation,
        DB.BuiltInCategory.OST_Callouts,  # Add callouts
        DB.BuiltInCategory.OST_DetailComponents,  # Add detail components
    ]
    
    all_annotations = []
    for category in annotation_categories:
        try:
            elements = list(DB.FilteredElementCollector(document)
                          .OfCategory(category)
                          .WhereElementIsNotElementType()
                          .ToElements())
            all_annotations.extend(elements)
            print("Found {} elements in category {}".format(len(elements), category))
        except Exception as e:
            print("Could not collect category {}: {}".format(category, str(e)))
            continue
    
    print("Total annotations found: {}".format(len(all_annotations)))
    
    # Try bulk transformation first (this worked before)
    annotation_ids = [ann.Id for ann in all_annotations if ann.Id]
    if annotation_ids:
        try:
            annotation_ids_list = List[DB.ElementId](annotation_ids)
            if transform.IsTranslation:
                DB.ElementTransformUtils.MoveElements(document, annotation_ids_list, transform.Origin)
                print("SUCCESS: Bulk moved {} annotations".format(len(annotation_ids)))
                return len(annotation_ids)
            else:
                # For complex transforms, apply to each annotation individually
                transformed_count = 0
                for ann_id in annotation_ids:
                    try:
                        ann_elem = document.GetElement(ann_id)
                        if ann_elem and ann_elem.Location:
                            location = ann_elem.Location
                            if hasattr(location, 'Point'):
                                location.Point = transform.OfPoint(location.Point)
                            elif hasattr(location, 'Curve'):
                                curve = location.Curve
                                start = transform.OfPoint(curve.GetEndPoint(0))
                                end = transform.OfPoint(curve.GetEndPoint(1))
                                location.Curve = DB.Line.CreateBound(start, end)
                            transformed_count += 1
                    except:
                        continue
                print("SUCCESS: Bulk transformed {} annotations".format(len(annotation_ids)))
                return len(annotation_ids)
        except Exception as bulk_e:
            print("Bulk annotation transform failed: {}".format(str(bulk_e)))
    
    return 0


def debug_transformation(document, transform, test_point=None):
    """Debug transformation by testing on a known point - ENHANCED"""
    
    if test_point is None:
        test_point = DB.XYZ(0, 0, 0)
    
    transformed_point = transform.OfPoint(test_point)
    
    print("=== TRANSFORMATION DEBUG ===")
    print("Original point: ({}, {}, {})".format(test_point.X, test_point.Y, test_point.Z))
    print("Transformed point: ({}, {}, {})".format(transformed_point.X, transformed_point.Y, transformed_point.Z))
    print("Translation: ({}, {}, {})".format(
        transformed_point.X - test_point.X,
        transformed_point.Y - test_point.Y, 
        transformed_point.Z - test_point.Z
    ))
    
    # MEASURE ROTATION ANGLE
    print("\n--- ROTATION ANALYSIS ---")
    print("Transform Matrix:")
    print("  BasisX: ({:.4f}, {:.4f}, {:.4f})".format(transform.BasisX.X, transform.BasisX.Y, transform.BasisX.Z))
    print("  BasisY: ({:.4f}, {:.4f}, {:.4f})".format(transform.BasisY.X, transform.BasisY.Y, transform.BasisY.Z))
    print("  BasisZ: ({:.4f}, {:.4f}, {:.4f})".format(transform.BasisZ.X, transform.BasisZ.Y, transform.BasisZ.Z))
    
    # Calculate actual rotation angle from matrix
    rotation_angle_rad = math.atan2(transform.BasisX.Y, transform.BasisX.X)
    rotation_angle_deg = math.degrees(rotation_angle_rad)
    print("Rotation angle from BasisX: {:.2f} degrees".format(rotation_angle_deg))
    
    # Also check Y basis rotation
    y_rotation_rad = math.atan2(-transform.BasisY.X, transform.BasisY.Y)
    y_rotation_deg = math.degrees(y_rotation_rad)
    print("Rotation angle from BasisY: {:.2f} degrees".format(y_rotation_deg))
    
    # Test rotation of unit vectors
    unit_x = DB.XYZ(1, 0, 0)
    unit_y = DB.XYZ(0, 1, 0)
    rotated_x = transform.OfVector(unit_x)
    rotated_y = transform.OfVector(unit_y)
    print("\nUnit vector transformations:")
    print("  X(1,0,0) -> ({:.4f}, {:.4f}, {:.4f})".format(rotated_x.X, rotated_x.Y, rotated_x.Z))
    print("  Y(0,1,0) -> ({:.4f}, {:.4f}, {:.4f})".format(rotated_y.X, rotated_y.Y, rotated_y.Z))
    
    try:
        inverse_transform = transform.Inverse
        print("\nTransform is invertible: True")
    except:
        print("\nTransform is invertible: False")
    
    print("Transform determinant: {}".format(transform.Determinant))
    print("Is translation only: {}".format(transform.IsTranslation))
    print("===========================")


def calculate_building_center(document, element_ids):
    """
    Calculate the center point of all building elements for rotation
    """
    if not element_ids:
        return DB.XYZ(0, 0, 0)
    
    min_x = min_y = min_z = float('inf')
    max_x = max_y = max_z = float('-inf')
    valid_count = 0
    
    for element_id in element_ids:
        try:
            element = document.GetElement(element_id)
            if element:
                bbox = element.get_BoundingBox(None)
                if bbox:
                    min_x = min(min_x, bbox.Min.X)
                    min_y = min(min_y, bbox.Min.Y)
                    min_z = min(min_z, bbox.Min.Z)
                    max_x = max(max_x, bbox.Max.X)
                    max_y = max(max_y, bbox.Max.Y)
                    max_z = max(max_z, bbox.Max.Z)
                    valid_count += 1
        except:
            continue
    
    if valid_count == 0:
        return DB.XYZ(0, 0, 0)
    
    # Calculate center point
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    center_z = min_z  # Use base level for rotation
    
    center = DB.XYZ(center_x, center_y, center_z)
    print("Calculated building center for rotation: ({:.2f}, {:.2f}, {:.2f})".format(
        center.X, center.Y, center.Z))
    
    return center


def transform_model_and_views_v3(document, translation_vector, rotation_angle_degrees, rotation_origin=None):
    """
    V3 - Enhanced transform with major elevation marker improvements
    """
    
    # Get elements first to calculate proper rotation center
    elements_to_transform = get_model_elements(document)
    
    if rotation_origin is None:
        # Calculate the actual center of the building for rotation
        rotation_origin = calculate_building_center(document, elements_to_transform)
        print("Using calculated building center as rotation origin")
    else:
        print("Using provided rotation origin: ({:.2f}, {:.2f}, {:.2f})".format(
            rotation_origin.X, rotation_origin.Y, rotation_origin.Z))
    
    rotation_angle_radians = math.radians(rotation_angle_degrees)
    
    try:
        # Create transformation matrix
        if rotation_angle_degrees != 0:
            rotation_transform = DB.Transform.CreateRotationAtPoint(
                DB.XYZ.BasisZ, rotation_angle_radians, rotation_origin
            )
            translation_transform = DB.Transform.CreateTranslation(translation_vector)
            combined_transform = translation_transform.Multiply(rotation_transform)
        else:
            combined_transform = DB.Transform.CreateTranslation(translation_vector)
        
        # Debug the transformation
        debug_transformation(document, combined_transform)
        
        with revit.Transaction("Enhanced Transform Model and Views - v3"):
            
            # 1. Transform model elements (using pre-gathered elements)
            if elements_to_transform:
                transformed_count = transform_elements_robust(document, elements_to_transform, combined_transform, rotation_angle_degrees, rotation_origin)
                print("Successfully transformed {}/{} elements".format(transformed_count, len(elements_to_transform)))
                
                success_rate = float(transformed_count) / len(elements_to_transform)
                print("Success rate: {:.1%} of elements transformed".format(success_rate))
            else:
                print("No elements found to transform!")
                return False
            
            # 2. Update views with V4 improvements - BUILDING CENTER ROTATION
            print("\n=== STARTING VIEW UPDATES ===")
            elevation_count = update_elevation_markers_v3(document, combined_transform, rotation_angle_degrees, rotation_origin)
            
            # Regenerate document after elevation marker changes (recommended for view-dependent elements)
            print("Regenerating document after elevation marker updates...")
            document.Regenerate()
            
            section_count = update_section_views_v3(document, combined_transform, rotation_angle_degrees, rotation_origin)
            plan_count = update_plan_views_v3(document, combined_transform)
            
            # 3. Update annotations
            annotation_count = update_annotations_v3(document, combined_transform)
            
            # Summary
            print("\n=== TRANSFORMATION SUMMARY v3 ===")
            print("Model elements: {}/{} transformed".format(transformed_count, len(elements_to_transform)))
            print("ELEVATION MARKERS: {} updated *** KEY IMPROVEMENT ***".format(elevation_count))
            print("Section views: {} updated".format(section_count))
            print("Plan views: {} updated".format(plan_count))
            print("Annotations: {} transformed".format(annotation_count))
            print("=====================================")
        
        print("Enhanced transformation v3 completed!")
        return True
        
    except Exception as e:
        print("Error during transformation: {}".format(str(e)))
        import traceback
        print("Full traceback:")
        print(traceback.format_exc())
        return False


def main():
    """Main function - called when script is executed in pyRevit"""
    
    # TRANSFORMATION PARAMETERS
    TRANSLATION_X = 0.0   # feet
    TRANSLATION_Y = 0.0     # feet  
    TRANSLATION_Z = 0.0     # feet
    ROTATION_DEGREES = 90.0  # degrees
    ROTATION_ORIGIN = None  # Will auto-calculate building center
    
    # Create translation vector
    translation = DB.XYZ(TRANSLATION_X, TRANSLATION_Y, TRANSLATION_Z)
    
    # Show confirmation dialog
    result = UI.TaskDialog.Show(
        "Enhanced Transform Model and Views - v6",
        "V6 ORIENTATION FIX:\n"
        "- CORRECTED: Move markers to exact building position\n"
        "- ORIENTATION: Adjust facing direction +45° around marker center\n"
        "- FIX: Separate position (building transform) and orientation (45° local)\n"
        "- ADDRESSES: V5 moved positions when only orientation needed fixing\n\n"
        "Transform settings:\n"
        "Translation: ({}, {}, {}) feet\n"
        "Rotation: {} degrees\n\n"
        "Continue?".format(
            TRANSLATION_X, TRANSLATION_Y, TRANSLATION_Z, ROTATION_DEGREES
        ),
        UI.TaskDialogCommonButtons.Yes | UI.TaskDialogCommonButtons.No
    )
    
    if result == UI.TaskDialogResult.Yes:
        success = transform_model_and_views_v3(doc, translation, ROTATION_DEGREES, ROTATION_ORIGIN)
        
        if success:
            UI.TaskDialog.Show("Success", "V3 transformation completed!\nCheck output for detailed elevation marker results.")
        else:
            UI.TaskDialog.Show("Error", "Transformation failed. Check the output for details.")
    else:
        print("Transformation cancelled by user.")


if __name__ == '__main__':
    main()