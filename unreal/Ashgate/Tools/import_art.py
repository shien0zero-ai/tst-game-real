"""Run in UnrealEditor-Cmd with -run=pythonscript -script=... .
Only creates project assets. Never writes engine assets or the Godot source art.
"""
import unreal as u
import pathlib, json
PROJECT = pathlib.Path(u.Paths.project_dir()).resolve()
ROOT = PROJECT.parents[1]
ART = "/Game/Art"
tools = u.AssetToolsHelpers.get_asset_tools()
eal = u.EditorAssetLibrary
mel = u.MaterialEditingLibrary
report = {"meshes":{},"surfaces":[],"source_units":"glTF metres -> UE centimetres", "normal_maps":"glTF importer conversion; explicit world normals flip green"}

def task(source, destination, options=None):
    t=u.AssetImportTask()
    t.filename=str(source); t.destination_path=destination; t.automated=True; t.replace_existing=False; t.save=True
    if options: t.options=options
    tools.import_asset_tasks([t])
    return [eal.load_asset(p) for p in t.imported_object_paths]

mesh_sources=[ROOT/"assets/models"/(n+".glb") for n in ("m1911_frame","m1911_slide","m1911_magazine","fps_hands_right","fps_hands_left")]
mesh_sources += list((ROOT/"assets/raid/models").glob("*.glb"))
mesh_sources += [ROOT/"assets/raid/enemy.glb"]
for source in mesh_sources:
    stable=ART+"/Meshes/"+source.stem
    if eal.does_asset_exist(stable):
        mesh=eal.load_asset(stable)
    else:
        pipeline=u.InterchangeGenericAssetsPipeline()
        pipeline.mesh_pipeline.combine_static_meshes_behavior=u.InterchangeCombineStaticMeshesBehavior.ALL
        pipeline.common_meshes_properties.force_all_mesh_as_type=u.InterchangeForceMeshType.IFMT_STATIC_MESH
        pipeline.animation_pipeline.import_animations=False
        stack=u.InterchangePipelineStackOverride(); stack.add_pipeline(pipeline)
        imported=task(source,ART+"/Imported/"+source.stem,stack)
        meshes=[a for a in imported if isinstance(a,u.StaticMesh)]
        if len(meshes)!=1:
            raise RuntimeError(f"Expected combined mesh {source}, got {[a.get_path_name() for a in meshes]}")
        eal.make_directory(ART+"/Meshes")
        if not eal.rename_asset(meshes[0].get_path_name(),stable): raise RuntimeError("rename failed "+stable)
        mesh=eal.load_asset(stable)
    bounds=mesh.get_bounds()
    report["meshes"][source.stem]={"origin":{k:getattr(bounds.origin,k) for k in ("x","y","z")},"extent_cm":{k:getattr(bounds.box_extent,k) for k in ("x","y","z")},"materials":[str(s.material_slot_name) for s in mesh.static_materials]}
    u.log("ASHGATE ART "+source.stem+" "+str(report["meshes"][source.stem]))
    eal.save_loaded_asset(mesh)

# Keep a skinned guard and the attributed, existing animation clips as well.
if not eal.does_asset_exist(ART+"/Characters/Guard"):
    pipeline=u.InterchangeGenericAssetsPipeline()
    pipeline.mesh_pipeline.import_static_meshes=False
    stack=u.InterchangePipelineStackOverride(); stack.add_pipeline(pipeline)
    imported=task(ROOT/"assets/raid/enemy.glb",ART+"/Characters/Imported",stack)
    for asset in imported:
        if isinstance(asset,u.SkeletalMesh):
            if not eal.rename_asset(asset.get_path_name(),ART+"/Characters/Guard"): raise RuntimeError("guard rename failed")
        elif isinstance(asset,u.AnimSequence):
            for clip in ("aim_idle","aim_walk","aim_run","idle","walk","run","death","hit","reload"):
                if asset.get_name() in (clip,"enemy"+clip,"enemy_"+clip):
                    eal.rename_asset(asset.get_path_name(),ART+"/Characters/"+clip)
                    break

# Repair names from the first import's suffix ambiguity, without reimporting art.
for short in ("idle","walk","run"):
    if not eal.does_asset_exist(ART+"/Characters/aim_"+short) and eal.does_asset_exist(ART+"/Characters/"+short) and eal.does_asset_exist(ART+"/Characters/Imported/enemy"+short):
        eal.rename_asset(ART+"/Characters/"+short,ART+"/Characters/aim_"+short)
for clip in ("aim_idle","aim_walk","aim_run","idle","walk","run","death","hit","reload"):
    source=ART+"/Characters/Imported/enemy"+clip
    if eal.does_asset_exist(source) and not eal.does_asset_exist(ART+"/Characters/"+clip):
        eal.rename_asset(source,ART+"/Characters/"+clip)

# Save usage flags on project materials instead of accepting fallback grey rendering.
for path in eal.list_assets(ART,recursive=True,include_folder=False):
    asset=eal.load_asset(path)
    if isinstance(asset,u.Material):
        asset.set_editor_property("used_with_nanite",True)
        asset.set_editor_property("used_with_skeletal_mesh",True)
        mel.recompile_material(asset)
        eal.save_loaded_asset(asset)
    if isinstance(asset,u.StaticMesh) and ("m1911_" in path or "fps_hands_" in path or asset.get_name() in ("lamp","generator")):
        settings=asset.get_editor_property("nanite_settings")
        settings.enabled=False
        asset.set_editor_property("nanite_settings",settings)
        eal.save_loaded_asset(asset)

def expression(mat, cls): return mel.create_material_expression(mat,cls)
def connect(a,output,b,input):
    if not mel.connect_material_expressions(a,output,b,input): raise RuntimeError("Cannot connect "+output+" -> "+input)
for surface in ("asphalt","concrete","brick","corrugated","steel","wood"):
    path=ART+"/Materials/"+surface
    textures={}
    for suffix in ("color","normalgl","roughness"):
        source=PROJECT/"Intermediate/ArtSource"/(surface+"_"+suffix+".png")
        texture_path=ART+"/Surfaces/"+surface+"_"+suffix
        textures[suffix]=eal.load_asset(texture_path) if eal.does_asset_exist(texture_path) else next(a for a in task(source,ART+"/Surfaces") if isinstance(a,u.Texture2D))
        tex=textures[suffix]
        if suffix=="normalgl":
            tex.set_editor_property("compression_settings",u.TextureCompressionSettings.TC_NORMALMAP); tex.set_editor_property("srgb",False); tex.set_editor_property("flip_green_channel",True)
        elif suffix=="roughness": tex.set_editor_property("srgb",False); tex.set_editor_property("compression_settings",u.TextureCompressionSettings.TC_MASKS)
        eal.save_loaded_asset(tex,only_if_is_dirty=False)
    mat=eal.load_asset(path) if eal.does_asset_exist(path) else tools.create_asset(surface,ART+"/Materials",u.Material,u.MaterialFactoryNew())
    mel.delete_all_material_expressions(mat)
    for suffix, prop in (("color",u.MaterialProperty.MP_BASE_COLOR),):
        tex=expression(mat,u.MaterialExpressionTextureObject); tex.texture=textures[suffix]
        if suffix=="roughness": tex.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_MASKS
        fn=expression(mat,u.MaterialExpressionMaterialFunctionCall)
        fn.set_material_function(eal.load_asset("/Engine/Functions/Engine_MaterialFunctions01/Texturing/WorldAlignedTexture"))
        size=expression(mat,u.MaterialExpressionConstant3Vector); size.constant=u.LinearColor(200,200,200)
        connect(tex,"",fn,"TextureObject"); connect(size,"",fn,"TextureSize")
        if not mel.connect_material_property(fn,"XYZ Texture",prop): raise RuntimeError("WorldAlignedTexture output changed")
    # Data maps have their own sampler type; WorldAlignedTexture's colour sampler
    # is unsuitable for masks. World-space XY coordinates match the ground at 2m.
    pos=expression(mat,u.MaterialExpressionWorldPosition)
    mask=expression(mat,u.MaterialExpressionComponentMask)
    for channel, enabled in (("r",True),("g",True),("b",False),("a",False)): mask.set_editor_property(channel,enabled)
    connect(pos,"",mask,"")
    mul=expression(mat,u.MaterialExpressionMultiply); mul.set_editor_property("const_b",.005); connect(mask,"",mul,"A")
    rough=expression(mat,u.MaterialExpressionTextureSample); rough.texture=textures["roughness"]; rough.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_MASKS
    connect(mul,"",rough,"UVs"); mel.connect_material_property(rough,"R",u.MaterialProperty.MP_ROUGHNESS)
    # OpenGL normals are converted to DirectX and softened for the first-pass blockout.
    norm=expression(mat,u.MaterialExpressionTextureSample); norm.texture=textures["normalgl"]; norm.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_NORMAL
    connect(mul,"",norm,"UVs")
    strength=expression(mat,u.MaterialExpressionMultiply); strength.set_editor_property("const_b",.3); connect(norm,"RGB",strength,"A")
    flat=expression(mat,u.MaterialExpressionAdd)
    base=expression(mat,u.MaterialExpressionConstant3Vector); base.constant=u.LinearColor(0,0,.7)
    connect(strength,"",flat,"A"); connect(base,"",flat,"B"); mel.connect_material_property(flat,"",u.MaterialProperty.MP_NORMAL)
    metal=expression(mat,u.MaterialExpressionConstant); metal.r=.8 if surface in ("steel","corrugated") else 0
    mel.connect_material_property(metal,"",u.MaterialProperty.MP_METALLIC)
    mel.recompile_material(mat); eal.save_loaded_asset(mat); report["surfaces"].append(surface)

# Explicit cloth materials keep glTF's authored roughness and woven normals,
# with darker charcoal albedo for first-person gloves instead of flat grey.
for part in ("fps_hands_right","fps_hands_left"):
    mesh=eal.load_asset(ART+"/Meshes/"+part)
    for index, slot in enumerate(mesh.static_materials):
        name=str(slot.material_slot_name)
        path=ART+"/Materials/"+name
        mat=eal.load_asset(path) if eal.does_asset_exist(path) else tools.create_asset(name,ART+"/Materials",u.Material,u.MaterialFactoryNew())
        mel.delete_all_material_expressions(mat)
        colors={"Hands_elastic_cuff":(.024,.027,.026),"Hands_stitched_seams":(.09,.095,.085),"Hands_woven_charcoal":(.035,.04,.045),"Hands_rubber_reinforcement":(.015,.018,.02),"Hands_cotton_sleeve":(.045,.058,.048)}
        col=expression(mat,u.MaterialExpressionConstant3Vector); col.constant=u.LinearColor(*colors[name])
        mel.connect_material_property(col,"",u.MaterialProperty.MP_BASE_COLOR)
        rough=expression(mat,u.MaterialExpressionConstant); rough.r=.94; mel.connect_material_property(rough,"",u.MaterialProperty.MP_ROUGHNESS)
        normal=eal.load_asset(ART+"/Imported/"+part+"/glove-weave")
        if normal:
            tex=expression(mat,u.MaterialExpressionTextureSample); tex.texture=normal; tex.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_NORMAL
            mel.connect_material_property(tex,"RGB",u.MaterialProperty.MP_NORMAL)
        mat.set_editor_property("used_with_nanite",True)
        mel.recompile_material(mat); eal.save_loaded_asset(mat); mesh.set_material(index,mat)
    eal.save_loaded_asset(mesh)

if not eal.does_asset_exist(ART+"/Materials/extract"):
    mat=tools.create_asset("extract",ART+"/Materials",u.Material,u.MaterialFactoryNew())
    c=expression(mat,u.MaterialExpressionConstant3Vector); c.constant=u.LinearColor(.06,.34,.15)
    mel.connect_material_property(c,"",u.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(c,"",u.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(mat); eal.save_loaded_asset(mat)
for source in (ROOT/"assets/audio").glob("*.wav"):
    if not eal.does_asset_exist(ART+"/Audio/"+source.stem): task(source,ART+"/Audio")

map_path="/Game/Maps/Depot04"
sub=u.get_editor_subsystem(u.LevelEditorSubsystem)
if not eal.does_asset_exist(map_path):
    sub.new_level(map_path)
    actors=u.get_editor_subsystem(u.EditorActorSubsystem)
    actors.spawn_actor_from_class(u.SkyAtmosphere,u.Vector(0,0,0))
    start=actors.spawn_actor_from_class(u.PlayerStart,u.Vector(-3900,-3300,100))
    start.set_actor_rotation(u.Rotator(0,36,0),False)
    sub.save_current_level()
eal.save_directory(ART,only_if_is_dirty=True,recursive=True)
(PROJECT/"Saved").mkdir(exist_ok=True)
(PROJECT/"Saved/art-import-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
u.log("ASHGATE ART IMPORT COMPLETE")
