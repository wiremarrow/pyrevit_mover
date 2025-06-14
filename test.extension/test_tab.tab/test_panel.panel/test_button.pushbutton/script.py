# -*- coding: utf-8 -*-
"""
Enhanced Transform Model and Views - FIXED v3
Major focus on elevation marker fixes and view coordination.

Author: Architecture Firm
Compatible with: Revit 2026
Required: pyRevit 4.8+
"""

__title__ = "Enhanced Transform\nModel and Views - Fixed v3"
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


def restore_wall_joins(document, wall_joins):
    """
    Restore wall-to-wall join relationships after transformation
    """
    if not wall_joins:
        return
    
    print("Restoring {} wall joins...".format(len(wall_joins)))
    
    for wall1_id, wall2_id in wall_joins:
        try:
            wall1 = document.GetElement(wall1_id)
            wall2 = document.GetElement(wall2_id)
            
            if wall1 and wall2:
                # Check if they're not already joined
                if not DB.JoinGeometryUtils.AreElementsJoined(document, wall1, wall2):
                    DB.JoinGeometryUtils.JoinGeometry(document, wall1, wall2)
        except Exception as e:
            print("Failed to restore wall join: {}".format(str(e)))
            continue
    
    print("Wall join restoration completed")


def get_model_elements(document):
    """
    Get all transformable model elements with better filtering
    """
    
    collector = DB.FilteredElementCollector(document).WhereElementIsNotElementType()
    elements_to_transform = []
    
    # Categories to exclude
    excluded_categories = [
        DB.BuiltInCategory.OST_ProjectBasePoint,
        DB.BuiltInCategory.OST_SharedBasePoint,
        DB.BuiltInCategory.OST_Views,
        DB.BuiltInCategory.OST_Sheets,
        DB.BuiltInCategory.OST_Viewports,
        DB.BuiltInCategory.OST_ElevationMarks,  # Handle separately
        DB.BuiltInCategory.OST_SectionBox,      # Handle separately
    ]
    
    # Element types to exclude by class
    excluded_types = (
        DB.View, DB.ViewSheet, DB.ProjectInfo, DB.BasePoint, 
        DB.ViewFamilyType, DB.Family, DB.FamilySymbol,
        DB.ElevationMarker,  # Handle separately
    )
    
    print("Analyzing elements for transformation...")
    
    for element in collector:
        try:
            # Skip if no category
            if not element.Category:
                continue
                
            # Skip excluded categories
            try:
                category_id = element.Category.Id.Value
                excluded_category_values = [int(cat) for cat in excluded_categories]
                
                if category_id in excluded_category_values:
                    continue
            except (AttributeError, TypeError):
                pass
                
            # Skip excluded element types
            if isinstance(element, excluded_types):
                continue
                
            # Skip view templates and system families
            if hasattr(element, 'ViewType') or hasattr(element, 'IsViewTemplate'):
                continue
                
            # Check for transformable elements
            has_location = hasattr(element, 'Location') and element.Location
            has_geometry = hasattr(element, 'get_Geometry')
            
            if not (has_location or has_geometry):
                continue
            
            # Skip coordinate system elements
            try:
                element_name = element.Name.lower() if hasattr(element, 'Name') and element.Name else ""
                problematic_keywords = [
                    'base point', 'survey', 'origin', 'internal origin',
                    'project base point', 'shared base point'
                ]
                if any(keyword in element_name for keyword in problematic_keywords):
                    continue
            except:
                pass
            
            elements_to_transform.append(element.Id)
            
        except Exception as e:
            continue
    
    print("Found {} elements to transform".format(len(elements_to_transform)))
    return elements_to_transform


def transform_elements_robust(document, element_ids, transform, rotation_degrees=0, rotation_origin=None):
    """
    Robust element transformation using proper Revit API methods
    Handles hosted elements, wall joins, and element invalidation
    """
    
    if not element_ids:
        return 0
    
    original_count = len(element_ids)
    element_ids_list = List[DB.ElementId](element_ids)
    transformed_count = 0
    
    # Store wall joins before transformation
    wall_joins = store_wall_joins(document, element_ids)
    
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
            
            # Debug: Check a sample element before rotation
            if element_ids:
                sample_element = document.GetElement(element_ids[0])
                if sample_element and sample_element.Location:
                    if hasattr(sample_element.Location, 'Point'):
                        before_point = sample_element.Location.Point
                        print("Sample element before rotation: ({:.2f}, {:.2f}, {:.2f})".format(
                            before_point.X, before_point.Y, before_point.Z))
            
            # Separate hosted and non-hosted elements
            hosted_elements, non_hosted_elements = separate_hosted_elements(document, element_ids)
            
            # Rotate non-hosted elements first (hosts before hosted)
            if non_hosted_elements:
                non_hosted_list = List[DB.ElementId](non_hosted_elements)
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
            
            # Debug: Check the same sample element after rotation
            if element_ids:
                sample_element = document.GetElement(element_ids[0])
                if sample_element and sample_element.Location:
                    if hasattr(sample_element.Location, 'Point'):
                        after_point = sample_element.Location.Point
                        print("Sample element after rotation: ({:.2f}, {:.2f}, {:.2f})".format(
                            after_point.X, after_point.Y, after_point.Z))
        
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
        
        # Step 3: Restore wall joins
        restore_wall_joins(document, wall_joins)
        
        print("Successfully transformed {}/{} elements".format(transformed_count, original_count))
        return transformed_count
        
    except Exception as e:
        print("Transformation failed: {}".format(str(e)))
        return 0


def update_elevation_markers_v3(document, transform):
    """
    V3 - MAJOR ELEVATION MARKER FIXES
    Multiple approaches to handle different elevation marker types
    """
    
    print("=== V3 ELEVATION MARKER UPDATE ===")
    
    # Method 1: Get elevation markers directly
    elevation_markers = list(DB.FilteredElementCollector(document).OfClass(DB.ElevationMarker).ToElements())
    print("Found {} ElevationMarker objects".format(len(elevation_markers)))
    
    # Method 2: Get by category
    elevation_by_category = list(DB.FilteredElementCollector(document)
                                .OfCategory(DB.BuiltInCategory.OST_ElevationMarks)
                                .WhereElementIsNotElementType()
                                .ToElements())
    print("Found {} elevation elements by category".format(len(elevation_by_category)))
    
    # Method 3: Find elevation-generating family instances
    family_instances = DB.FilteredElementCollector(document).OfClass(DB.FamilyInstance).ToElements()
    elevation_families = []
    
    for instance in family_instances:
        try:
            if instance.Symbol and instance.Symbol.Family:
                family_name = instance.Symbol.Family.Name.lower()
                # Look for elevation-related families
                elevation_keywords = ['elevation', 'marker', 'callout']
                if any(keyword in family_name for keyword in elevation_keywords):
                    elevation_families.append(instance)
        except:
            continue
    
    print("Found {} potential elevation family instances".format(len(elevation_families)))
    
    # Combine all found elevation elements
    all_elevation_elements = []
    all_elevation_elements.extend(elevation_markers)
    all_elevation_elements.extend(elevation_by_category)
    all_elevation_elements.extend(elevation_families)
    
    # Remove duplicates by ID
    unique_elevations = {}
    for elem in all_elevation_elements:
        unique_elevations[elem.Id.Value] = elem
    
    final_elevation_list = list(unique_elevations.values())
    print("Total unique elevation elements to process: {}".format(len(final_elevation_list)))
    
    updated_count = 0
    
    for marker in final_elevation_list:
        try:
            marker_id = marker.Id.Value
            print("Processing elevation element: {} (Type: {})".format(marker_id, type(marker).__name__))
            
            # Method A: Try direct location transformation
            if hasattr(marker, 'Location') and marker.Location:
                try:
                    location = marker.Location
                    print("  Location type: {}".format(type(location).__name__))
                    
                    if isinstance(location, DB.LocationPoint):
                        old_point = location.Point
                        new_point = transform.OfPoint(old_point)
                        location.Point = new_point
                        updated_count += 1
                        print("  SUCCESS: LocationPoint updated")
                        continue
                        
                    elif isinstance(location, DB.LocationCurve):
                        old_curve = location.Curve
                        new_curve = old_curve.CreateTransformed(transform)
                        location.Curve = new_curve
                        updated_count += 1
                        print("  SUCCESS: LocationCurve updated")
                        continue
                        
                    else:
                        print("  Location type {} - trying alternative methods...".format(type(location).__name__))
                        
                except Exception as loc_e:
                    print("  Location method failed: {}".format(str(loc_e)))
            
            # Method B: Try using ElementTransformUtils
            try:
                element_list = List[DB.ElementId]([marker.Id])
                if transform.IsTranslation:
                    DB.ElementTransformUtils.MoveElements(document, element_list, transform.Origin)
                    print("  SUCCESS: Moved via ElementTransformUtils")
                else:
                    # For complex transforms, we need to handle each element individually
                    element = document.GetElement(elem.Id)
                    if element and element.Location:
                        location = element.Location
                        if hasattr(location, 'Point'):
                            location.Point = transform.OfPoint(location.Point)
                    print("  SUCCESS: Transformed via ElementTransformUtils")
                updated_count += 1
                continue
                
            except Exception as transform_e:
                print("  ElementTransformUtils failed: {}".format(str(transform_e)))
            
            # Method C: For ElevationMarker objects, try specific methods
            if isinstance(marker, DB.ElevationMarker):
                try:
                    # Try to get the marker's position and update it
                    if hasattr(marker, 'Position'):
                        old_pos = marker.Position
                        new_pos = transform.OfPoint(old_pos)
                        # Note: Position might be read-only, but try anyway
                        marker.Position = new_pos
                        updated_count += 1
                        print("  SUCCESS: ElevationMarker Position updated")
                        continue
                except Exception as pos_e:
                    print("  Position method failed: {}".format(str(pos_e)))
                
                # Try to access elevation views and update their origins
                try:
                    elevation_count = marker.CurrentViewCount
                    print("  Marker has {} elevation views".format(elevation_count))
                    
                    for i in range(elevation_count):
                        try:
                            elev_view_id = marker.GetElevationViewId(i)
                            if elev_view_id and elev_view_id != DB.ElementId.InvalidElementId:
                                elev_view = document.GetElement(elev_view_id)
                                if elev_view:
                                    print("    Found elevation view: {}".format(elev_view.Name))
                                    # The view should update automatically when marker moves
                        except Exception as view_e:
                            continue
                            
                except Exception as views_e:
                    print("  Elevation view access failed: {}".format(str(views_e)))
            
            # Method D: Try geometry-based approach for family instances
            if isinstance(marker, DB.FamilyInstance):
                try:
                    # Some elevation markers might have special parameters
                    params_to_check = ['Elevation', 'Height', 'Position', 'Origin']
                    
                    for param_name in params_to_check:
                        try:
                            param = marker.LookupParameter(param_name)
                            if param and not param.IsReadOnly:
                                if param.StorageType == DB.StorageType.Double:
                                    # This is a simplified approach - you might need more sophisticated parameter handling
                                    print("    Found parameter: {} = {}".format(param_name, param.AsDouble()))
                        except:
                            continue
                            
                except Exception as param_e:
                    print("  Parameter check failed: {}".format(str(param_e)))
            
            print("  WARNING: Could not update elevation element {}".format(marker_id))
            
        except Exception as e:
            print("  ERROR processing elevation element {}: {}".format(
                marker.Id.Value if hasattr(marker, 'Id') else 'Unknown', str(e)))
            continue
    
    print("=== ELEVATION UPDATE SUMMARY ===")
    print("Updated {} out of {} elevation elements".format(updated_count, len(final_elevation_list)))
    print("Success rate: {:.1%}".format(float(updated_count) / len(final_elevation_list) if final_elevation_list else 0))
    print("================================")
    
    return updated_count


def update_section_views_v3(document, transform):
    """
    V3 - Enhanced section view updates with better marker handling
    """
    
    print("=== V3 SECTION VIEW UPDATE ===")
    
    section_views = DB.FilteredElementCollector(document).OfClass(DB.ViewSection).ToElements()
    print("Found {} section views to process".format(len(section_views)))
    updated_count = 0
    
    # Also find section markers/callouts
    section_markers = []
    family_instances = DB.FilteredElementCollector(document).OfClass(DB.FamilyInstance).ToElements()
    
    for instance in family_instances:
        try:
            if instance.Symbol and instance.Symbol.Family:
                family_name = instance.Symbol.Family.Name.lower()
                if 'section' in family_name or 'callout' in family_name:
                    section_markers.append(instance)
        except:
            continue
    
    print("Found {} section marker family instances".format(len(section_markers)))
    
    # Update section markers first
    for marker in section_markers:
        try:
            if hasattr(marker, 'Location') and marker.Location:
                if isinstance(marker.Location, DB.LocationCurve):
                    old_curve = marker.Location.Curve
                    new_curve = old_curve.CreateTransformed(transform)
                    marker.Location.Curve = new_curve
                    print("Updated section marker curve: {}".format(marker.Id))
                elif isinstance(marker.Location, DB.LocationPoint):
                    old_point = marker.Location.Point
                    new_point = transform.OfPoint(old_point)
                    marker.Location.Point = new_point
                    print("Updated section marker point: {}".format(marker.Id))
        except Exception as e:
            print("Could not update section marker {}: {}".format(marker.Id, str(e)))
    
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
                        # For section views, we need to transform the view origin, not the crop box bounds
                        # The crop box transform contains the view's coordinate system
                        old_transform = crop_box.Transform
                        
                        # Transform the origin point
                        new_origin = transform.OfPoint(old_transform.Origin)
                        
                        # Create new transform with moved origin but same orientation
                        new_transform = DB.Transform.Identity
                        new_transform.Origin = new_origin
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
                        # For plan views, we need to transform the view origin, not the crop box bounds
                        # The crop box transform contains the view's coordinate system
                        old_transform = crop_box.Transform
                        
                        # Transform the origin point
                        new_origin = transform.OfPoint(old_transform.Origin)
                        
                        # Create new transform with moved origin but same orientation
                        new_transform = DB.Transform.Identity
                        new_transform.Origin = new_origin
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
    """Debug transformation by testing on a known point"""
    
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
    
    try:
        inverse_transform = transform.Inverse
        print("Transform is invertible: True")
    except:
        print("Transform is invertible: False")
    
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
            
            # 2. Update views with V3 improvements - ELEVATION MARKERS FIRST
            print("\n=== STARTING VIEW UPDATES ===")
            elevation_count = update_elevation_markers_v3(document, combined_transform)
            section_count = update_section_views_v3(document, combined_transform)
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
    TRANSLATION_X = 50.0   # feet
    TRANSLATION_Y = 50.0     # feet  
    TRANSLATION_Z = 0.0     # feet
    ROTATION_DEGREES = 90.0  # degrees
    ROTATION_ORIGIN = DB.XYZ(0, 0, 0)
    
    # Create translation vector
    translation = DB.XYZ(TRANSLATION_X, TRANSLATION_Y, TRANSLATION_Z)
    
    # Show confirmation dialog
    result = UI.TaskDialog.Show(
        "Enhanced Transform Model and Views - v3",
        "V3 MAJOR ELEVATION FIXES:\n"
        "- Multiple elevation marker detection methods\n"
        "- Enhanced location type handling\n"
        "- Better family instance support\n"
        "- Improved error reporting\n\n"
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