import io
import apiclient.http
import apiclient.errors
import httplib2
import httplib
import random
import time

def upload(service, data, bucket_name, object_name, mimetype="application/binary", chunksize=1024*1024, retries=5, progressCb=None):
    fh = io.BytesIO(data)
    try:
        # request = service.buckets().get(bucket=bucket_name, projection='full')
        # info = request.execute()
        # print "NANANANANANAANA", info
        # raise Exception

        media = apiclient.http.MediaIoBaseUpload(fh, mimetype=mimetype, chunksize=chunksize, resumable=True)
        request = service.objects().insert(
            bucket=bucket_name,
            body={
                "acl": [{'entity': 'allUsers', 'role': 'READER'}],
#                "predefinedAcl": "projectPrivate",
                "metadata": {"Access-Control-Allow-Origin": "*"}},
            name=object_name,
            media_body=media)

        progressless_iters = 0
        response = None
        while response is None:
            error = None
            try:
                progress, response = request.next_chunk()
                if progress and progressCb:
                    progressCb(progress)
            except apiclient.errors.HttpError, err:
                error = err
                if err.resp.status < 500:
                    raise
            except Exception, err:
                error = err

            if error:
                progressless_iters += 1

                if progressless_iters > retries:
                    raise error

                sleeptime = random.random() * (2**progressless_iters)
                time.sleep(sleeptime)
            else:
                progressless_iters = 0

        # request = service.objectAccessControls().list(
        #     bucket=bucket_name,
        #     object=object_name)
        # print "ZZZZZ", request.execute()

        # request = service.objectAccessControls().insert(
        #     bucket=bucket_name,
        #     object=object_name,
        #     body={'entity': 'allUsers', 'role': 'READER'})
        # request.execute()

        return response
    finally:
      fh.close()

