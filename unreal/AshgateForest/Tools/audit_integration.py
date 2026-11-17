import unreal as u,pathlib,json
P=pathlib.Path(u.Paths.project_dir());sub=u.get_editor_subsystem(u.StaticMeshEditorSubsystem);r={}
for folder in ['FieldFinish','Integration']:
 r[folder]={}
 for name in ['field_frame','field_slide','field_magazine']:
  m=u.EditorAssetLibrary.load_asset('/Game/Forest/'+folder+'/Meshes/'+name);b=sub.get_lod_build_settings(m,0)
  r[folder][name]={'recompute_normals':b.recompute_normals,'recompute_tangents':b.recompute_tangents,'high_precision_tangents':b.use_high_precision_tangent_basis,'full_precision_uvs':b.use_full_precision_u_vs,'vertices':sub.get_number_verts(m,0),'nanite':m.get_editor_property('nanite_settings').enabled}
  if folder=='Integration':assert not b.recompute_normals and b.use_high_precision_tangent_basis and b.use_full_precision_u_vs
(P/'Saved/integration-final-audit.json').write_text(json.dumps(r,indent=2));u.log('INTEGRATION FINAL AUDIT PASS '+json.dumps(r))
