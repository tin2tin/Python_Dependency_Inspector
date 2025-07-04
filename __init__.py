bl_info = {
    "name": "Python Dependency Inspector",
    "author": "tintwotin",
    "version": (1, 3, 0),
    "blender": (3, 0, 0),
    "location": "Edit > Preferences > Add-ons > Python Dependency Inspector",
    "description": "A self-contained tool to find which Python library installed another. All UI is inside the addon's preferences.",
    "warning": "",
    "doc_url": "",
    "category": "Development",
}

import bpy
import re

try:
    from packaging.version import Version, InvalidVersion
    from packaging.requirements import Requirement, InvalidRequirement
    PACKAGING_LIB_AVAILABLE = True
except ImportError:
    PACKAGING_LIB_AVAILABLE = False

from importlib.metadata import distributions


# --- Property Groups to hold the search state ---

class DI_ResultItem(bpy.types.PropertyGroup):
    """Holds a single result item: the name of a requiring package and its specifier."""
    name: bpy.props.StringProperty()
    specifier: bpy.props.StringProperty()

class DI_SearchProperties(bpy.types.PropertyGroup):
    """Holds the user's search query and the list of results."""
    target_package: bpy.props.StringProperty(
        name="Package Name",
        description="The name of the installed library to check (e.g., 'numpy')",
        default="urllib3"
    )
    
    target_version: bpy.props.StringProperty(
        name="Target Version",
        description="Optional: Find libraries requiring this specific version (e.g. '1.26.0')",
    )
    
    results: bpy.props.CollectionProperty(type=DI_ResultItem)
    last_search_was_empty: bpy.props.BoolProperty(default=False)


# --- The Operator (Core Logic) ---

class DEPENDENCY_INSPECTOR_OT_Find(bpy.types.Operator):
    """Searches the Blender Python environment for packages that require the target package"""
    bl_idname = "dependency_inspector.find"
    bl_label = "Find Requiring Libraries"
    bl_options = {'REGISTER'} # No UNDO needed for a preference change

    def execute(self, context):
        prefs = context.preferences.addons[__name__].preferences
        # The state is now stored directly in the preferences
        search_props = prefs.search_props
        
        target_pkg = search_props.target_package.strip().lower()
        target_ver_str = search_props.target_version.strip()

        if not target_pkg:
            self.report({'WARNING'}, "Please enter a package name.")
            return {'CANCELLED'}

        target_version_obj = None
        if prefs.enable_version_search and target_ver_str and PACKAGING_LIB_AVAILABLE:
            try:
                target_version_obj = Version(target_ver_str)
            except InvalidVersion:
                self.report({'ERROR'}, f"Invalid version format: '{target_ver_str}'. Please use format like '1.2.3'.")
                return {'CANCELLED'}

        search_props.results.clear()
        search_props.last_search_was_empty = False
        requiring_packages = []
        normalized_target = target_pkg.replace("-", "_")

        for dist in distributions():
            if not dist.requires: continue
            for req_string in dist.requires:
                try:
                    req = Requirement(req_string)
                    if req.name.lower().replace("-", "_") == normalized_target:
                        version_match = not target_version_obj or req.specifier.contains(target_version_obj, prereleases=True)
                        if version_match:
                            requiring_packages.append((dist.metadata['Name'], str(req.specifier) or "any"))
                except (InvalidRequirement, AttributeError):
                    pass # Ignore malformed requirement strings

        if requiring_packages:
            msg = f"Found {len(requiring_packages)} dependents for '{target_pkg}'"
            if target_version_obj: msg += f" matching version '{target_ver_str}'"
            self.report({'INFO'}, msg)
            for name, spec in sorted(requiring_packages):
                item = search_props.results.add(); item.name = name; item.specifier = spec
        else:
            self.report({'INFO'}, f"No dependents found for '{target_pkg}' with the specified criteria.")
            search_props.last_search_was_empty = True

        return {'FINISHED'}


# --- Addon Preferences with All UI ---

class DEPENDENCY_INSPECTOR_AP_Preferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    enable_version_search: bpy.props.BoolProperty(
        name="Enable Version Search",
        description="Allow searching by a specific version number",
        default=False
    )
    
    # Pointer to our PropertyGroup that holds the search state
    search_props: bpy.props.PointerProperty(type=DI_SearchProperties)
    
    def draw(self, context):
        layout = self.layout
        
        # --- Feature Settings ---
        layout.label(text="Settings")
        box = layout.box()
        col = box.column()
        col.prop(self, "enable_version_search")
        if not PACKAGING_LIB_AVAILABLE:
            col.active = False
            error_box = layout.box()
            error_box.label(text="Version search requires the 'packaging' library.", icon='ERROR')

        layout.separator()

        # --- The Main Inspector UI ---
        layout.label(text="Dependency Inspector")
        main_box = layout.box()
        
        # We access the search properties via the 'self' reference to the preferences
        search_props = self.search_props

        col = main_box.column(align=True)
        row = col.row(align=True)
        row.prop(search_props, "target_package", text="")
        
        # Conditionally show the version input based on the preference setting
        if self.enable_version_search and PACKAGING_LIB_AVAILABLE:
             row.prop(search_props, "target_version", text="Version")

        col.operator(DEPENDENCY_INSPECTOR_OT_Find.bl_idname, text="Find Dependents", icon='VIEWZOOM')

        # --- Display Results ---
        if search_props.results:
            results_box = main_box.box()
            results_box.label(text="Required By:", icon='INFO')
            for item in search_props.results:
                row = results_box.row()
                row.label(text=f"- {item.name}")
                row.label(text=f"({item.specifier})", icon='FILE_SCRIPT')
                
        elif search_props.last_search_was_empty:
             main_box.box().label(text="No direct dependents found.", icon='QUESTION')


# --- Registration ---

classes = (
    DI_ResultItem,
    DI_SearchProperties,
    DEPENDENCY_INSPECTOR_OT_Find,
    DEPENDENCY_INSPECTOR_AP_Preferences,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
