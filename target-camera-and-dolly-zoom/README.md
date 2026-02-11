# Target Camera and Dolly Zoom for Blender

Blenderのカメラに以下の機能を提供します。

1. 標準カメラとターゲットカメラの切替
2. ドリーズーム機能

## ターゲットカメラ機能

- 目標点（ターゲット）を注視するターゲットカメラと、標準カメラの切り換え
- カメラからターゲットまでの距離を調整
- ターゲットの回転をカメラに一致

![ターゲットカメラ動作](images/target_camera_01.gif)

## ドリーズーム機能

- **ターゲットカメラ時のみ有効**
- カメラのドリー（前後移動）と、ズームを同時調整

![ドリーズーム動作](images/dolly_zoom_01.gif)

## インストール方法（Blender 4.2.7 LTS）

1. 右上のCodeから、zipファイルをダウンロード
2. Blenderを起動し、 `Edit > Preferences > Get Extensions` を開く
3. 右上のトグルボタンから`Install from Disk` をクリックし、ダウンロードしたzipファイルを選択
4. チェックボックスをオンにして有効化

追加される場所はカメラのデータプロパティ
![追加される場所](images/addon_location_01.jpg)

## 仕様

このアドオンは「漫画のカメラアングル検討」のために作りました。  
シンプルに、複雑なリグを組まないことを優先しています。
そのため、カメラそのものにターゲットコンストレインを適応しています。

つまり、**「カメラのロール」は無視されます**。

どうしてもカメラロールを維持したい場合は、このアドオンではなく、以下のようにリグを組むのが良いと思います。

- Position Empty
  - Rotation Empty
    - Roll Empty
      - Camera
- Target Empty


Rotation Emptyにトラックコンストレインを適応、ロール角度はRoll Emptyで制御
