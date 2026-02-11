bl_info = {
    "name": "Target Camera Tools",
    "author": "Teitetsu",
    "version": (1, 0),
    "blender": (4, 2, 7), 
    "location": "Properties > Camera > Lens",
    "description": "ターゲットカメラの作成とドリーズーム機能",
    "warning": "",
    "category": "Camera",
}

import bpy
import mathutils
import math

########################################
# Constant 共通定数
########################################

CONSTRAINT_NAME = "Target_Camera"
TGT_CUSTOM_PROPERTY_NAME = "Is_Camera_Target"

########################################
# Function 共通関数
########################################

# ターゲットカメラの判断
def is_target_camera(cam_obj):
    if not cam_obj or cam_obj.type != 'CAMERA':
        return False
    
    # コンストレインの確認
    con = cam_obj.constraints.get(CONSTRAINT_NAME)
    if not con :
        return False
    if not con.enabled:
        return False

    # カメラターゲットの確認
    target_obj = con.target
    if not target_obj:
        return False

    if target_obj.type != 'EMPTY' and TGT_CUSTOM_PROPERTY_NAME in target_obj:
        return False

    return True

# データプロパティからカメラオブジェクトを取得
def get_cam_from_props(props):
    cam_data = props.id_data
    return next((o for o in bpy.data.objects if o.data == cam_data), None)

# カメラオブジェクトから、カメラターゲットを取得
def get_target_obj(cam_obj):
    if not cam_obj: return None

    # 1. コンストレインから取得
    track_constraint = cam_obj.constraints.get(CONSTRAINT_NAME)
    if track_constraint:
        target_obj = track_constraint.target
        if target_obj and TGT_CUSTOM_PROPERTY_NAME in target_obj:
            return track_constraint.target
    
    # 2. 子から取得を試みる
    for child in cam_obj.children:
        if TGT_CUSTOM_PROPERTY_NAME in child:
            return child
    return None

# ターゲットが、複数のカメラのターゲットになってるか確認
def is_target_shared(target_obj, owner_cam_obj):
    if not target_obj: return False
    
    for obj in bpy.data.objects:
        if obj.type == 'CAMERA' and obj != owner_cam_obj:
            con = obj.constraints.get(CONSTRAINT_NAME)
            if con and con.target == target_obj:
                return True 
    return False

########################################
# ターゲットカメラのロジック
########################################


# ターゲットカメラ、標準カメラの変換
def toggle_camera_mode(cam_obj):

    TARGET_NAME = f"{cam_obj.name}_Target"
    track_constraint = cam_obj.constraints.get(CONSTRAINT_NAME)
    target_obj =get_target_obj(cam_obj)

    if not track_constraint:
        #トラックコンストレインが無い場合の処理
        # A. 子のターゲットがある場合：ペアレント解除
        if target_obj or is_target_shared(target_obj,cam_obj):
            # 1. 現在のマトリクスを一時保管
            matrix_copy = target_obj.matrix_world.copy()        
            # 2. 親子関係を解除
            target_obj.parent = None        
            # 3. 保持していたワールド行列を再代入
            target_obj.matrix_world = matrix_copy
            target_obj.hide_set(False)
        
        # B. 子のターゲットが無い場合：新規ターゲット作成
        else:
            # カメラ前方5ｍ、エンプティを作成
            target_loc = cam_obj.matrix_world @ mathutils.Vector((0, 0, -5))

            empty_data = None # エンプティにデータは不要
            target_obj = bpy.data.objects.new(TARGET_NAME, empty_data)
            target_obj.empty_display_type = 'PLAIN_AXES'
            target_obj.empty_display_size = 0.1
            target_obj.location = target_loc

            # カメラをシーンにリンク
            coll = cam_obj.users_collection[0] if cam_obj.users_collection else bpy.context.scene.collection
            coll.objects.link(target_obj)

            target_obj[TGT_CUSTOM_PROPERTY_NAME] = True

        # カメラにトラックコンストレインを追加
        cam_const = cam_obj.constraints.new(type='TRACK_TO')
        cam_const.name = CONSTRAINT_NAME
        cam_const.target = target_obj
        cam_const.track_axis = 'TRACK_NEGATIVE_Z'

        # ターゲットの名前修正（名前ズレ対策）
        target_obj.name = TARGET_NAME


        
    #「トラックコンストレインが無効になってるだけ」の処理
    elif not track_constraint.enabled and target_obj:
        if target_obj.parent != cam_obj:
            track_constraint.enabled = True
        else:
            matrix_copy = target_obj.matrix_world.copy()  
            target_obj.parent = None        
            target_obj.matrix_world = matrix_copy
            target_obj.hide_set(False)
            track_constraint.enabled = True           


    # ターゲットカメラ→標準カメラへ切替
    else:
        target_obj = track_constraint.target
        # コンストレインを適応
        bpy.ops.constraint.apply(constraint=CONSTRAINT_NAME, owner='OBJECT')
 
        # 複数の親が無い場合のみ、エンプティをカメラの子にする（位置を維持）
        if not is_target_shared(target_obj,cam_obj):
            if target_obj:
                target_obj.parent = cam_obj
                target_obj.matrix_parent_inverse = cam_obj.matrix_world.inverted()
                target_obj.hide_set(True)
                # ターゲットの名前修正（名前ズレ対策）
                target_obj.name = TARGET_NAME

# ターゲットの距離を調整
def change_target_distance(cam_obj, target_obj, distance):
    # 1. ターゲットのワールド行列を分解
    loc, rot, scale =target_obj.matrix_world.decompose()
    # 2. 新しい位置を計算
    target_new_loc = cam_obj.matrix_world @ mathutils.Vector((0, 0, -distance))
    # 3. マトリクスを再構築し、設定
    target_obj.matrix_world = mathutils.Matrix.LocRotScale(target_new_loc, rot, scale)

# 2オブジェクト間の距離を計算
def distacne_between_AB(obj_a, obj_b):
    return (obj_a.matrix_world.to_translation() - obj_b.matrix_world.to_translation()).length


########################################
# ドリーズームのロジック
########################################

# 距離から焦点距離(mm)を計算
def get_lens_from_distance(cam_obj, distance, constant_height):
    sensor_width = cam_obj.data.sensor_width
    # 焦点距離 f = (sensor_width * distance) / (2 * constant_height)
    return (sensor_width * distance) / (2 * constant_height)

# 焦点距離(mm)から距離を計算
def get_distance_from_lens(cam_obj, lens_mm, constant_height):
    sensor_width = cam_obj.data.sensor_width
    # 距離 d = (2 * constant_height * lens_mm) / sensor_width
    return (2 * constant_height * lens_mm) / sensor_width

# ドリーズームのメイン計算ロジック
def dolly_zoom_logic(cam_obj, target_obj, new_distance=None, new_lens=None):
    cam_data = cam_obj.data
    current_distance = distacne_between_AB(cam_obj,target_obj)
    
    # 現在の画面内での被写体サイズ（基準高さ）を算出
    # constant_height = (distance * sensor_width) / (2 * focal_length)
    constant_height = (current_distance * cam_data.sensor_width) / (2 * cam_data.lens)

    if new_distance is not None:
        # 1. 距離が変わった場合：カメラを移動させ、レンズを調整
        target_loc = target_obj.matrix_world.to_translation()
        direction = (cam_obj.matrix_world.to_translation() - target_loc).normalized()
        cam_obj.location = target_loc + (direction * new_distance)
        cam_data.lens = get_lens_from_distance(cam_obj, new_distance, constant_height)
        
    elif new_lens is not None:
        # 2. レンズが変わった場合：レンズをセットし、カメラの距離を調整
        cam_data.lens = new_lens
        required_distance = get_distance_from_lens(cam_obj, new_lens, constant_height)
        target_loc = target_obj.matrix_world.to_translation()
        direction = (cam_obj.matrix_world.to_translation() - target_loc).normalized()
        cam_obj.location = target_loc + (direction * required_distance)


########################################
# プロパティ設定
########################################

# カメラに追加するプロパティ
class CameraTargetProperties(bpy.types.PropertyGroup):
    
    # 1. 「ターゲットカメラ切替」の設定
    #  Getter（チェックボックスの状態を取得）
    def get_use_target(self):
        cam_obj = get_cam_from_props(self)
        return is_target_camera(cam_obj)

    # Setter(チェック時の動作)
    def set_use_target(self, value):
        cam_obj = get_cam_from_props(self)
        if cam_obj:
            # 現在の状態とクリックされた値が違う場合のみ切り替え
            if is_target_camera(cam_obj) != value:
                toggle_camera_mode(cam_obj)

    use_target_camera: bpy.props.BoolProperty(
        name="ターゲットカメラ切替",
        description="ターゲットカメラと標準カメラの切り替え",
        get=get_use_target,
        set=set_use_target
    )

    # 2. 「ターゲットの距離」の設定
    # Getter（距離を取得）
    def get_distance(self):
        cam_obj = get_cam_from_props(self)
        target_obj = get_target_obj(cam_obj)
        
        if cam_obj and target_obj:
            return distacne_between_AB(cam_obj,target_obj)
        return 5.0 # ターゲットがない時のデフォルト値

    # Setter(距離を設定)
    def set_distance(self, value):
        cam_obj = get_cam_from_props(self)
        target_obj = get_target_obj(cam_obj)
        
        if cam_obj and target_obj:
            change_target_distance(cam_obj, target_obj, value)

    target_distance: bpy.props.FloatProperty(
        name="ターゲットの距離",
        description="カメラからターゲットまでの距離を調整",
        default=5.0,
        min=0.01,
        unit="LENGTH",
        get=get_distance,
        set=set_distance
    )

    # Setter(カメラの位置と焦点距離を設定)
    def set_dollyzoom_from_distance(self, value):
        cam_obj = get_cam_from_props(self)
        target_obj = get_target_obj(cam_obj)
        
        if cam_obj and target_obj:
            dolly_zoom_logic(cam_obj, target_obj, new_distance=value)

    dolly_zoom_from_distance: bpy.props.FloatProperty(
        name="距離を基準",
        description="距離を元にレンズを調整",
        default=5.0,
        min=0.01,
        unit="LENGTH",
        get=get_distance,
        set=set_dollyzoom_from_distance
    )

    # Getter（カメラの焦点距離(mm)を取得）
    def get_lens(self):
        cam_obj = get_cam_from_props(self)
        if cam_obj and cam_obj.data:
            return cam_obj.data.lens
        return 50.0
    
    # Setter(カメラの位置と焦点距離を設定)
    def set_dollyzoom_from_lens(self, value):
        cam_obj = get_cam_from_props(self)
        target_obj = get_target_obj(cam_obj)

        if cam_obj and target_obj:
            dolly_zoom_logic(cam_obj, target_obj, new_lens=value)


    dolly_zoom_from_lens: bpy.props.FloatProperty(
        name="焦点距離を基準",
        description="レンズを元にカメラ位置を調整",
        default=50.0,
        min=1,
        unit="CAMERA",
        get=get_lens,
        set=set_dollyzoom_from_lens
    )


########################################
# オペレータ設定（カメラに追加するボタン）
########################################

# カメラターゲットを選択
class CAMERA_OT_select_target(bpy.types.Operator):
    bl_idname = "camera.select_target"
    bl_label = "ターゲットを選択"

    def execute(self, context):
        cam_obj = context.object
        target_obj = get_target_obj(cam_obj)
        if target_obj:
            bpy.ops.object.select_all(action='DESELECT')
            target_obj.select_set(True)
            bpy.context.view_layer.objects.active = target_obj
        return {'FINISHED'}

# ターゲットの向きを、カメラに合わせる
class CAMERA_OT_match_rotation(bpy.types.Operator):
    bl_idname = "camera.match_target_rotation"
    bl_label = "ターゲットの向き合わせ"

    def execute(self, context):
        cam_obj = context.object
        target_obj = get_target_obj(cam_obj)
        if cam_obj and target_obj:
            cam_rot = cam_obj.matrix_world.to_quaternion()
            loc, rot, scale =target_obj.matrix_world.decompose()
            target_obj.matrix_world = mathutils.Matrix.LocRotScale(loc, cam_rot, scale)
        return {'FINISHED'}

# ドリーズームパネル開閉用のオペレータ
class CAMERA_OT_toggle_dollyzoom_panel(bpy.types.Operator):
    bl_idname = "camera.toggle_dollyzoom_panel"
    bl_label = "ドリーズーム設定"
    
    def execute(self, context):
        context.window_manager.dolly_camera_ui_expanded = not context.window_manager.dolly_camera_ui_expanded
        return {'FINISHED'}

########################################
# UI設定
########################################

# 既存のレンズパネルにターゲットカメラのUIを追加
def draw_camera_target_lens_ui(self, context):

    layout = self.layout
    cam = context.object
    if not cam or cam.type != 'CAMERA': return
    
    props = cam.data.target_cam_props
    is_active = is_target_camera(cam)
    _is_expanded = context.window_manager.dolly_camera_ui_expanded
    
    layout.separator()
    box_tgtCam = layout.box()
    box_tgtCam.label(text="ターゲットカメラ", icon='VIEW_CAMERA')
    
    # 切替チェックボックス
    box_tgtCam.prop(props, "use_target_camera", toggle=False)

    # ターゲットの距離
    col1 = box_tgtCam.column(align=True)
    col1.enabled = is_active
    col1.prop(props, "target_distance")
    # ターゲット選択、回転合わせ
    row = box_tgtCam.row(align=True)
    row.enabled = is_active
    row.operator("camera.match_target_rotation", icon='ORIENTATION_PARENT')
    row.operator("camera.select_target", icon='RESTRICT_SELECT_OFF')

    # ドリーズームの設定
    
    icon = 'TRIA_DOWN' if _is_expanded else 'TRIA_RIGHT'

    box_dollyZoom = layout.box()
    box_dollyZoom.enabled = is_active

    toggleRow = box_dollyZoom.row(align=True)
    toggleRow.alignment = "LEFT"
    toggleRow.operator("camera.toggle_dollyzoom_panel",text="",icon=icon,emboss=False)
    toggleRow.label(text="ドリーズーム設定",icon='UV_SYNC_SELECT')
    
    col2 = box_dollyZoom.column(align=True)

    if _is_expanded:
        col2.prop(props, "dolly_zoom_from_distance")
        col2.prop(props, "dolly_zoom_from_lens")



########################################
# Register、Blenderに登録
########################################


classes = (
    CameraTargetProperties,
    CAMERA_OT_select_target,
    CAMERA_OT_match_rotation,
    CAMERA_OT_toggle_dollyzoom_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # カメラのプロパティ拡張
    bpy.types.Camera.target_cam_props = bpy.props.PointerProperty(type=CameraTargetProperties)
    
    # レンズパネルにUI追加
    bpy.types.DATA_PT_lens.append(draw_camera_target_lens_ui)

    # ドリーズームパネル開閉用のブール
    bpy.types.WindowManager.dolly_camera_ui_expanded = bpy.props.BoolProperty(default=False)

def unregister():
    # 拡張したプロパティの削除
    bpy.types.DATA_PT_lens.remove(draw_camera_target_lens_ui)
    del bpy.types.Camera.target_cam_props
    del bpy.types.WindowManager.dolly_camera_ui_expanded

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    try:
        unregister()
    except:
        pass
    register()
