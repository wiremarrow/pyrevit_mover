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


def transform_elements_robust(document, element_ids, transform):
    """
    Robust element transformation using the proven method
    """
    
    if not element_ids:
        return 0
        
    element_ids_list = List[DB.ElementId](element_ids)
    
    try:
        if transform.IsTranslation:
            print("Using MoveElements for translation...")
            translation = transform.Origin
            DB.ElementTransformUtils.MoveElements(document, element_ids_list, translation)
            print("Bulk move successful!")
            return len(element_ids)
        else:
            print("Complex transformation - using TransformElements...")
            DB.ElementTransformUtils.TransformElements(document, element_ids_list, transform)
            print("Bulk transformation successful!")
            return len(element_ids)
    except Exception as e:
        print("Bulk transformation failed: {}".format(str(e)))
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
                    DB.ElementTransformUtils.TransformElements(document, element_list, transform)
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
                DB.ElementTransformUtils.TransformElements(document, annotation_ids_list, transform)
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


def transform_model_and_views_v3(document, translation_vector, rotation_angle_degrees, rotation_origin=None):
    """
    V3 - Enhanced transform with major elevation marker improvements
    """
    
    if rotation_origin is None:
        rotation_origin = DB.XYZ(0, 0, 0)
    
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
            
            # 1. Transform model elements (proven to work)
            elements_to_transform = get_model_elements(document)
            if elements_to_transform:
                transformed_count = transform_elements_robust(document, elements_to_transform, combined_transform)
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
    ROTATION_DEGREES = 0.0  # degrees
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