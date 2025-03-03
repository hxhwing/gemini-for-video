## How to run


### 1. Create Repository
创建一个 Container Repository 
```
gcloud artifacts repositories create gemini-for-video \
    --repository-format=docker \
    --location=us-central1 
```

### 2. Modify parameters in app.py
请修改 `app.py` 中的 PROJECT, REGION, GCS BUCKET等信息 
```
## Please use your own PROJECT_ID, REGION, and GCS_BUCKET
PROJECT_ID = "hxhdemo"
REGION = "us-central1"
gcs_path = "gs://hxhdemo"
```

### 3. Build container image
进入代码所在的路径，执行以下命令，使用 Cloud Build 构建容器镜像，并存放到 Artifacts Registry 仓库 (请替换成上一步创建的镜像仓库链接)
```
gcloud builds submit --region=us-central1 --tag us-central1-docker.pkg.dev/hxhdemo/gemini-for-video/gemini-for-video:latest
```

### 4. Deploy to Cloud Run
需要指定一个 GCS Bucket 作为挂载路径，存放视频处理结果，替换下面 ```bucket=xxx``` 中的xxx

如果不使用 GCS，或者不使用 Cloud Run，而是直接在本地运行，则需要将```app.py```中的`output_path`更换为本地路径
```
gcloud run deploy gemini-for-video \
 --image us-central1-docker.pkg.dev/hxhdemo/gemini-for-video/gemini-for-video:latest \
 --allow-unauthenticated \
 --port 8501 \
 --cpu 2 \
 --memory 8Gi \
 --region us-central1 \
 --add-volume name=hxhdemo,type=cloud-storage,bucket=hxhdemo \
 --add-volume-mount volume=hxhdemo,mount-path=/mnt/gcsfuse
```

Deploy 完成之后，将会获得一个 Service URL，可直接访问
```
Deploying container to Cloud Run service [gemini-for-video] in project [hxhdemo] region [us-central1]
✓ Deploying... Done.
  ✓ Creating Revision...
  ✓ Routing traffic...
  ✓ Setting IAM Policy...
Done.
Service [gemini-for-video] revision [gemini-for-video-00002-bzs] has been deployed and is serving 100 percent of traffic.
Service URL: https://gemini-for-video-75934506457.us-central1.run.app
```