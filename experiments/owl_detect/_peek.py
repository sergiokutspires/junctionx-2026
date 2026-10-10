import json, cv2, numpy as np, sys, os
root='C:/Users/alifa/learning/junctionx-sensei'
p=json.load(open(root+'/data/raw/planogram.json',encoding='utf-8'))
cams={}
for s,v in p.items():
    for cam,c in v['cameras'].items(): cams[cam]=c['products']
out=root+'/experiments/owl_detect/sheets/peek'
os.makedirs(out,exist_ok=True)
for cam in sys.argv[1:]:
    fs=sorted(os.listdir(f'{root}/data/raw/images/{cam}'))
    for f in [fs[0], fs[len(fs)//2]]:
        im=cv2.imread(f'{root}/data/raw/images/{cam}/{f}')
        for a in cams[cam]:
            ic=a['image_coordinates']; q=np.array([ic['top_left'],ic['top_right'],ic['bottom_right'],ic['bottom_left']],np.int32)
            cv2.polylines(im,[q],True,(0,255,255),2)
            c=q.mean(0).astype(int); cv2.putText(im,a['area_id'].split('_')[1],tuple(c),0,1,(0,0,255),2)
        cv2.imwrite(f'{out}/{cam}_{f}',cv2.resize(im,(960,540)))
