import os

import pytest
from ffmpeg_tools.codecs import VideoCodec
from ffmpeg_tools.formats import Container, list_supported_frame_rates
from ffmpeg_tools.frame_rate import FrameRate
from ffmpeg_tools.validation import validate_resolution
from ffmpeg_tools.exceptions import InvalidResolution, \
    UnsupportedVideoCodecConversion, InvalidFrameRate
from parameterized import parameterized

from golem.tools.ci import ci_skip
from tests.apps.ffmpeg.task.ffmpeg_integration_base import \
    FfmpegIntegrationBase, \
    create_split_and_merge_with_codec_change_test_name, \
    create_split_and_merge_with_resolution_change_test_name, \
    create_split_and_merge_with_frame_rate_change_test_name, \
    create_split_and_merge_with_different_subtask_counts_test_name
from tests.apps.ffmpeg.task.utils.ffprobe_report import FuzzyDuration, \
    parse_ffprobe_frame_rate
from tests.apps.ffmpeg.task.utils.simulated_transcoding_operation import \
    SimulatedTranscodingOperation


# flake8: noqa
# pylint: disable=line-too-long,bad-whitespace
VIDEO_FILES = [
    # Files from transcoding-video-bundle
    {"resolution": [512, 288],   "container": Container.c_WEBM,     "video_codec": VideoCodec.VP8,       "key_frames": 1,    "path": "videos/good/basen-out8[vp8,512x288,10s,v1a0s0d0,i1p247b0,25fps].webm"},
    {"resolution": [512, 288],   "container": Container.c_WEBM,     "video_codec": VideoCodec.VP9,       "key_frames": 1,    "path": "videos/good/basen-out9[vp9,512x288,10s,v1a0s0d0,i1p247b0,25fps].webm"},
    {"resolution": [1920, 1080], "container": Container.c_MPEG,     "video_codec": VideoCodec.MPEG_2,    "key_frames": 15,   "path": "videos/good/beachfront-dandelion[mpeg2video+mp2,1920x1080,20s,v1a1s0d0,i161p321b0,23.976fps][segment1of11].mpeg"},
    {"resolution": [1920, 1080], "container": Container.c_ASF,      "video_codec": VideoCodec.WMV3,      "key_frames": 1,    "path": "videos/good/beachfront-mooncloseup[wmv3,1920x1080,34s,v1a0s0d0,i7p786b0,24fps][segment1of7].wmv"},
    {"resolution": [1920, 1080], "container": Container.c_ASF,      "video_codec": VideoCodec.WMV3,      "key_frames": 1,    "path": "videos/good/beachfront-sleepingbee[wmv3+wmapro,1920x1080,47s,v1a1s0d0,i10p1116b0,24fps][segment1of10].wmv"},
    {"resolution": [1920, 960],  "container": Container.c_MATROSKA, "video_codec": VideoCodec.HEVC,      "key_frames": 1,    "path": "videos/good/h265files-alps[hevc+aac,1920x960,16s,v1a1s0d0,i2p79b319,25fps][segment1of2].mkv"},
    {"resolution": [854, 480],   "container": Container.c_MATROSKA, "video_codec": VideoCodec.MSMPEG4V2, "key_frames": 4,    "path": "videos/good/matroska-test1[msmpeg4v2+mp3,854x480,87s,v1a1s0d0,i25p2071b0,24fps][segment1of10].mkv"},
    {"resolution": [1024, 576],  "container": Container.c_MATROSKA, "video_codec": VideoCodec.H_264,     "key_frames": 5,    "path": "videos/good/matroska-test5[h264+aac+aac,1024x576,47s,v1a2s8d0,i46p552b506,24fps][segment1of10].mkv"},
    {"resolution": [1280, 720],  "container": Container.c_ASF,      "video_codec": VideoCodec.WMV3,      "key_frames": 11,   "path": "videos/good/natureclip-fireandembers[wmv3+wmav2,1280x720,63s,v1a1s0d0,i351p1539b0,29.97fps][segment1of13].wmv"},
    {"resolution": [176, 144],   "container": Container.c_3GP,      "video_codec": VideoCodec.H_263,     "key_frames": 7,    "path": "videos/good/sample-bigbuckbunny[h263+amr_nb,176x144,41s,v1a1s0d0,i51p559b0,15fps][segment1of9].3gp"},
    # ffmpeg does not transcode this file correctly. It’s missing a lot of
    # frames. We have decided to disable it because the file is likely
    # damaged, nonstandard or uses a format feature that ffmpeg can’t handle.
    # The broken file is unfortunately the expected result because that’s
    # how ffmpeg processes the file - it’s not a bug in our code. In the
    # future it would be better to find a way to weed out files like this at
    # the validation stage
    # {"resolution": [1280, 720],  "container": Container.c_MATROSKA, "video_codec": VideoCodec.MPEG_4,    "key_frames": 1,    "path": "videos/good/sample-bigbuckbunny[mpeg4+aac,1280x720,4s,v1a1s0d0,i1p146b0,25fps].mkv"},
    {"resolution": [320, 240],   "container": Container.c_3GP,      "video_codec": VideoCodec.MPEG_4,    "key_frames": 11,   "path": "videos/good/sample-bigbuckbunny[mpeg4+aac,320x240,15s,v1a1s0d0,i32p343b0,25fps][segment1of3].3gp"},
    {"resolution": [640, 368],   "container": Container.c_MP4,      "video_codec": VideoCodec.MPEG_4,    "key_frames": 1,    "path": "videos/good/sample-bigbuckbunny[mpeg4+aac,640x368,6s,v1a1s0d0,i1p159b0,25fps].mp4"},
    {"resolution": [560, 320],   "container": Container.c_AVI,      "video_codec": VideoCodec.MPEG_4,    "key_frames": 13,   "path": "videos/good/standalone-bigbuckbunny[mpeg4+mp3,560x320,6s,v1a1s0d0,i14p152b0,30fps][segment1of2].avi"},
    {"resolution": [180, 140],   "container": Container.c_ASF,      "video_codec": VideoCodec.WMV3,      "key_frames": 1,    "path": "videos/good/standalone-catherine[wmv3+wmav2,180x140,42s,v1a1s0d0,i6p626b0,_][segment1of6].wmv"},
    {"resolution": [400, 300],   "container": Container.c_MOV,      "video_codec": VideoCodec.H_264,     "key_frames": 1,    "path": "videos/good/standalone-dlppart2[h264+aac,400x300,129s,v1a1s0d0,i17p1027b2814,29.97fps][segment1of17].mov"},
    {"resolution": [720, 480],   "container": Container.c_IPOD,     "video_codec": VideoCodec.H_264,     "key_frames": 2,    "path": "videos/good/standalone-dolbycanyon[h264+aac,720x480,38s,v1a1s0d0,i7p326b808,29.97fps][segment1of5].m4v"},
    {"resolution": [720, 480],   "container": Container.c_FLV,      "video_codec": VideoCodec.FLV1,      "key_frames": 13,   "path": "videos/good/standalone-grb2[flv1,720x480,28s,v1a0s0d0,i75p760b0,29.9697fps][segment1of6].flv"},
    {"resolution": [720, 480],   "container": Container.c_IPOD,     "video_codec": VideoCodec.H_264,     "key_frames": 1,    "path": "videos/good/standalone-grb2[h264,720x480,28s,v1a0s0d0,i6p226b603,29.97fps][segment1of4].m4v"},
    {"resolution": [720, 480],   "container": Container.c_MPEG,     "video_codec": VideoCodec.MPEG_2,    "key_frames": 47,   "path": "videos/good/standalone-grb2[mpeg2video,720x480,28s,v1a0s0d0,i47p234b554,29.97fps].mpg"},
    {"resolution": [720, 480],   "container": Container.c_SVCD,     "video_codec": VideoCodec.MPEG_2,    "key_frames": 13,   "path": "videos/good/standalone-grb2[mpeg2video,720x480,28s,v1a0s0d0,i77p758b0,29.97fps][segment1of6].vob"},
    {"resolution": [720, 480],   "container": Container.c_ASF,      "video_codec": VideoCodec.WMV2,      "key_frames": 13,   "path": "videos/good/standalone-grb2[wmv2,720x480,28s,v1a0s0d0,i76p759b0,29.97fps][segment1of6].wmv"},
    {"resolution": [1920, 1080], "container": Container.c_FLV,      "video_codec": VideoCodec.FLV1,      "key_frames": 10,   "path": "videos/good/standalone-jellyfish[flv1,1920x1080,30s,v1a0s0d0,i76p824b0,29.9697fps][segment1of8].flv"},
    {"resolution": [1408, 1152], "container": Container.c_3GP,      "video_codec": VideoCodec.H_263,     "key_frames": 10,   "path": "videos/good/standalone-jellyfish[h263,1408x1152,30s,v1a0s0d0,i76p824b0,29.97fps][segment1of8].3gp"},
    {"resolution": [1920, 1080], "container": Container.c_MATROSKA, "video_codec": VideoCodec.HEVC,      "key_frames": 1,    "path": "videos/good/standalone-jellyfish[hevc,1920x1080,30s,v1a0s0d0,i4p224b672,29.97fps][segment1of4].mkv"},
    # This file fails at the transcoding step because the result of the
    # extract+split step is incorrect - it still contains an audio track.
    # We have decided to disable this case because the file is likely
    # damaged, nonstandard or uses a format feature that ffmpeg can’t handle.
    # The failure is the expected result unless we find a way to block this
    # file via validations.“
    # {"resolution": [384, 288],   "container": Container.c_MPEG,     "video_codec": VideoCodec.MPEG_1,    "key_frames": 8,    "path": "videos/good/standalone-lion[mpeg1video+mp2,384x288,117s,v1a1s0d0,i175p525b2097,23.976fps][segment1of24].mpeg"},
    {"resolution": [320, 240],   "container": Container.c_MP4,      "video_codec": VideoCodec.H_264,     "key_frames": 1,    "path": "videos/good/standalone-p6090053[h264+aac,320x240,30s,v1a1s0d0,i2p94b279,12.5fps][segment1of2].mp4"},
    {"resolution": [320, 240],   "container": Container.c_MOV,      "video_codec": VideoCodec.MJPEG,     "key_frames": 38,   "path": "videos/good/standalone-p6090053[mjpeg+pcm_u8,320x240,30s,v1a1s0d0,i375p0b0,12.5fps][segment1of10].mov"},
    {"resolution": [480, 270],   "container": Container.c_FLV,      "video_codec": VideoCodec.FLV1,      "key_frames": 11,   "path": "videos/good/standalone-page18[flv1+mp3,480x270,216s,v1a1s0d0,i452p4949b0,25fps][segment1of44].flv"},
    {"resolution": [352, 288],   "container": Container.c_3GP,      "video_codec": VideoCodec.H_263,     "key_frames": 11,   "path": "videos/good/standalone-page18[h263+amr_nb,352x288,216s,v1a1s0d0,i452p4949b0,25fps][segment1of44].3gp"},
    {"resolution": [480, 270],   "container": Container.c_IPOD,     "video_codec": VideoCodec.H_264,     "key_frames": 2,    "path": "videos/good/standalone-page18[h264+aac,480x270,216s,v1a1s0d0,i46p5355b0,25fps][segment1of43].m4v"},
    {"resolution": [480, 270],   "container": Container.c_AVI,      "video_codec": VideoCodec.MPEG_4,    "key_frames": 11,   "path": "videos/good/standalone-page18[mpeg4+mp3,480x270,216s,v1a1s0d0,i452p4949b0,25fps][segment1of44].avi"},
    {"resolution": [1920, 1080], "container": Container.c_MPEGTS,   "video_codec": VideoCodec.H_264,     "key_frames": 11,   "path": "videos/good/standalone-panasonic[h264+ac3,1920x1080,46s,v1a1s1d0,i96p288b768,25fps][segment1of10].mts"},
    {"resolution": [1920, 1080], "container": Container.c_AVI,      "video_codec": VideoCodec.MPEG_4,    "key_frames": 11,   "path": "videos/good/standalone-panasonic[mpeg4+mp3,1920x1080,46s,v1a1s0d0,i99p1053b0,25fps][segment1of10].avi"},
    {"resolution": [352, 288],   "container": Container.c_3GP,      "video_codec": VideoCodec.H_263,     "key_frames": 13,   "path": "videos/good/standalone-small[h263+amr_nb,352x288,6s,v1a1s0d0,i14p152b0,30fps][segment1of2].3gp"},
    {"resolution": [560, 320],   "container": Container.c_MPEGTS,   "video_codec": VideoCodec.H_264,     "key_frames": 1,    "path": "videos/good/standalone-small[h264+ac3,560x320,6s,v1a1s0d0,i1p46b119,29.97fps].mts"},
    {"resolution": [560, 320],   "container": Container.c_MATROSKA, "video_codec": VideoCodec.H_264,     "key_frames": 1,    "path": "videos/good/standalone-small[h264+vorbis,560x320,6s,v1a1s0d0,i1p46b119,30fps].mkv"},
    {"resolution": [560, 320],   "container": Container.c_SVCD,     "video_codec": VideoCodec.MPEG_2,    "key_frames": 13,   "path": "videos/good/standalone-small[mpeg2video+mp2,560x320,6s,v1a1s0d0,i14p152b0,30fps][segment1of2].vob"},
    {"resolution": [560, 320],   "container": Container.c_WEBM,     "video_codec": VideoCodec.VP8,       "key_frames": 1,    "path": "videos/good/standalone-small[vp8+vorbis,560x320,6s,v1a1s0d0,i1p165b0,30fps].webm"},
    {"resolution": [560, 320],   "container": Container.c_ASF,      "video_codec": VideoCodec.WMV2,      "key_frames": 13,   "path": "videos/good/standalone-small[wmv2+wmav2,560x320,6s,v1a1s0d0,i14p152b0,30fps][segment1of2].wmv"},
    {"resolution": [1280, 720],  "container": Container.c_FLV,      "video_codec": VideoCodec.FLV1,      "key_frames": 11,   "path": "videos/good/standalone-startrails[flv1+mp3,1280x720,21s,v1a1s0d0,i45p484b0,25fps][segment1of5].flv"},
    {"resolution": [704, 576],   "container": Container.c_3GP,      "video_codec": VideoCodec.H_263,     "key_frames": 11,   "path": "videos/good/standalone-startrails[h263+amr_nb,704x576,21s,v1a1s0d0,i45p484b0,25fps][segment1of5].3gp"},
    {"resolution": [1280, 720],  "container": Container.c_WEBM,     "video_codec": VideoCodec.VP9,       "key_frames": 1,    "path": "videos/good/standalone-startrails[vp9+opus,1280x720,21s,v1a1s0d0,i5p524b0,25fps][segment1of5].webm"},
    {"resolution": [704, 576],   "container": Container.c_3GP,      "video_codec": VideoCodec.H_263,     "key_frames": 12,   "path": "videos/good/standalone-tra3106[h263,704x576,17s,v1a0s0d0,i53p456b0,29.97fps][segment1of5].3gp"},
    {"resolution": [720, 496],   "container": Container.c_AVI,      "video_codec": VideoCodec.MJPEG,     "key_frames": 30,   "path": "videos/good/standalone-tra3106[mjpeg,720x496,17s,v1a0s0d0,i509p0b0,29.97fps][segment1of17].avi"},
    {"resolution": [320, 240],   "container": Container.c_ASF,      "video_codec": VideoCodec.WMV1,      "key_frames": 2,    "path": "videos/good/standalone-video1[wmv1+wmav2,320x240,12s,v1a1s0d0,i3p348b0,30fps][segment1of2].wmv"},
    {"resolution": [320, 240],   "container": Container.c_FLV,      "video_codec": VideoCodec.FLV1,      "key_frames": 4,    "path": "videos/good/standalone-videosample[flv1,320x240,59s,v1a0s0d0,i45p179b0,_][segment1of12].flv"},
    {"resolution": [320, 240],   "container": Container.c_MPEGTS,   "video_codec": VideoCodec.H_264,     "key_frames": 1,    "path": "videos/good/standalone-videosample[h264,320x240,59s,v1a0s0d0,i1p56b167,29.97fps].mts"},
    {"resolution": [320, 240],   "container": Container.c_ASF,      "video_codec": VideoCodec.WMV2,      "key_frames": 1,    "path": "videos/good/techslides-small[wmv2+wmav2,320x240,6s,v1a1s0d0,i1p165b0,30fps].wmv"},
    {"resolution": [640, 360],   "container": Container.c_WEBM,     "video_codec": VideoCodec.VP8,       "key_frames": 3,    "path": "videos/good/webmfiles-bigbuckbunny[vp8+vorbis,640x360,32s,v1a1s0d0,i26p786b0,25fps][segment1of7].webm"},
    {"resolution": [640, 480],   "container": Container.c_ASF,      "video_codec": VideoCodec.WMV3,      "key_frames": 1,    "path": "videos/good/wfu-katamari[wmv3+wmav2,640x480,10s,v1a1s0d0,i2p298b0,29.97fps][segment1of2].wmv"},
    {"resolution": [3840, 2160], "container": Container.c_WEBM,     "video_codec": VideoCodec.VP8,       "key_frames": 13,   "path": "videos/good/wikipedia-globaltemp[vp8+vorbis,3840x2160,37s,v1a1s0d0,i92p1011b0,30fps][segment1of8].webm"},
    {"resolution": [1920, 1080], "container": Container.c_WEBM,     "video_codec": VideoCodec.VP8,       "key_frames": 1,    "path": "videos/good/wikipedia-tractor[vp8+vorbis,1920x1080,28s,v1a1s0d0,i6p684b0,1000fps][segment1of5].webm"},
    {"resolution": [854, 480],   "container": Container.c_WEBM,     "video_codec": VideoCodec.VP9,       "key_frames": 1,    "path": "videos/good/wikipedia-tractor[vp9+opus,854x480,28s,v1a1s0d0,i3p687b0,25fps][segment1of3].webm"},
    {"resolution": [854, 480],   "container": Container.c_WEBM,     "video_codec": VideoCodec.AV1,       "key_frames": 1880, "path": "videos/good/woolyss-llamadrama[av1+opus,854x480,87s,v1a1s0d0,i0p0b0,24fps].webm"},
    {"resolution": [1920, 1080], "container": Container.c_MOV,      "video_codec": VideoCodec.MJPEG,     "key_frames": 1192, "path": "videos/bad/beachfront-moonandclouds[mjpeg,1920x1080,50s,v1a0s0d1,i1192p0b0,24fps].mov"},
    {"resolution": [1920, 1080], "container": Container.c_MOV,      "video_codec": VideoCodec.MJPEG,     "key_frames": 792,  "path": "videos/bad/beachfront-mooncloseup[mjpeg,1920x1080,33s,v1a0s0d1,i792p0b0,23.976fps].mov"},
    {"resolution": [1280, 720],  "container": Container.c_MATROSKA, "video_codec": VideoCodec.THEORA,    "key_frames": 36,   "path": "videos/bad/matroska-test4[theora+vorbis,1280x720,_,v1a1s0d0,i36p1606b0,24fps].mkv"},
    {"resolution": [1920, 1080], "container": Container.c_MOV,      "video_codec": VideoCodec.H_264,     "key_frames": 7,    "path": "videos/bad/natureclip-relaxriver[h264+aac,1920x1080,20s,v1a1s0d1,i7p593b0,29.97fps].mov"},
    {"resolution": [704, 576],   "container": Container.c_3GP,      "video_codec": VideoCodec.H_263,     "key_frames": 96,   "path": "videos/bad/standalone-dolbycanyon[h263+amr_nb,704x576,38s,v1a1s0d0,i96p1045b0,29.97fps].3gp"},
    {"resolution": [720, 480],   "container": Container.c_SVCD,     "video_codec": VideoCodec.MPEG_2,    "key_frames": 77,   "path": "videos/bad/standalone-dolbycanyon[mpeg2video+ac3,720x480,38s,v1a1s0d1,i77p304b760,29.97fps].vob"},
    {"resolution": [560, 320],   "container": Container.c_MPEG,     "video_codec": VideoCodec.MPEG_2,    "key_frames": 14,   "path": "videos/bad/standalone-small[mpeg2video+mp2,560x320,6s,v1a1s0d1,i14p152b0,30fps].mpg"},
    {"resolution": [720, 496],   "container": Container.c_MPEG,     "video_codec": VideoCodec.MPEG_2,    "key_frames": 59,   "path": "videos/bad/standalone-tra3106[mpeg2video,720x496,17s,v1a0s0d1,i59p450b0,29.97fps].mpeg"},
    {"resolution": [320, 240],   "container": Container.c_MPEG,     "video_codec": VideoCodec.MPEG_2,    "key_frames": 1188, "path": "videos/bad/standalone-videosample[mpeg2video,320x240,59s,v1a0s0d1,i1188p13066b0,240fps].mpg"},
    {"resolution": [560, 320],   "container": Container.c_OGG,      "video_codec": VideoCodec.THEORA,    "key_frames": 3,    "path": "videos/bad/techslides-small[theora+vorbis,560x320,6s,v1a1s0d1,i3p163b0,30fps].ogv"},
]
# pylint: enable=line-too-long,bad-whitespace


@ci_skip
# FIXME: These tests should be re-enabled once all the fixes needed
# to make them pass are done and merged.
@pytest.mark.skip("Files from transcoding-video-bundle disabled for now")
# pylint: disable=too-many-ancestors
class TestFfmpegIntegrationFullBundleSet(FfmpegIntegrationBase):

    # flake8: noqa
    # pylint: disable=line-too-long
    _IGNORED_ATTRIBUTES_OF_BROKEN_FILE = {
        # The merge step (using ffmpeg’s concat demuxer) changes FPS from 29.97
        # to 30. This happens only for this particular file and there does not
        # seem to be anything unusual about the input file itself. We have
        # decided to ignore this problem for now because we can’t do anything
        # about it and it’s likely to be a bug in ffmpeg. So bad output is
        # unfortunately the expected result here.
        'standalone-tra3106[mjpeg,720x496,17s,v1a0s0d0,i1525p1016b1016,29.97fps][segment1of17].avi': {'video': {'frame_rate'}},
        # This wmv3/wmv file has incorrect FPS in metadata (or at least ffprobe
        # returns an incorrect value). This makes ffmpeg (incorrectly) double
        # the number of frames while keeping the FPS in output file metadata the
        # same as in the original. We can’t help it. We’re going to assume that
        # this is the expected result, i.e. garbage in, garbage out.”
        'standalone-catherine[wmv3+wmav2,180x140,42s,v1a1s0d0,i637p1257b631,_][segment1of6].wmv': {'video': {'frame_rate'}},
    }
    # pylint: enable=line-too-long

    @parameterized.expand(
        (
            (video, video_codec, container)
            for video in VIDEO_FILES  # pylint: disable=undefined-variable
            for video_codec, container in (
                (VideoCodec.FLV1, Container.c_FLV),
                (VideoCodec.H_264, Container.c_AVI),
                (VideoCodec.HEVC, Container.c_MP4),
                (VideoCodec.MJPEG, Container.c_MOV),
                (VideoCodec.MPEG_1, Container.c_MPEG),
                (VideoCodec.MPEG_2, Container.c_MPEG),
                (VideoCodec.MPEG_4, Container.c_MPEGTS),
                (VideoCodec.THEORA, Container.c_OGG),    # unsupported
                (VideoCodec.VP8, Container.c_WEBM),
                (VideoCodec.VP9, Container.c_MATROSKA),
                (VideoCodec.WMV1, Container.c_ASF),
                (VideoCodec.WMV2, Container.c_ASF),
            )
        ),
        name_func=create_split_and_merge_with_codec_change_test_name
    )
    @pytest.mark.slow
    def test_split_and_merge_with_codec_change(self,
                                               video,
                                               video_codec,
                                               container):
        source_codec = video["video_codec"]
        operation = SimulatedTranscodingOperation(
            task_executor=self,
            experiment_name="codec change",
            resource_dir=self.RESOURCES,
            tmp_dir=self.tempdir,
            dont_include_in_option_description=["resolution"])
        operation.attach_to_report_set(self._ffprobe_report_set)
        operation.request_video_codec_change(video_codec)
        operation.request_container_change(container)
        operation.request_resolution_change(video["resolution"])
        operation.exclude_from_diff(
            FfmpegIntegrationBase.ATTRIBUTES_NOT_PRESERVED_IN_CONVERSIONS)
        operation.exclude_from_diff({'video': {'frame_count'}})
        operation.enable_treating_missing_attributes_as_unchanged()

        filename = os.path.basename(video['path'])
        if filename in self._IGNORED_ATTRIBUTES_OF_BROKEN_FILE:
            operation.exclude_from_diff(
                self._IGNORED_ATTRIBUTES_OF_BROKEN_FILE[filename])

        if not Container.is_supported(video['container'].value):
            pytest.skip("Source container not supported")
        if not Container.is_supported(container.value):
            pytest.skip("Target container not supported")
        if not video['container'].is_supported_video_codec(source_codec.value):
            pytest.skip("Source video codec not supported by the container")
        if not container.is_supported_video_codec(video_codec.value):
            pytest.skip("Target video codec not supported by the container")

        if source_codec.can_convert(video_codec.value):
            (_input_report, _output_report, diff) = operation.run(
                video["path"])
            self.assertEqual(diff, [])
        else:
            with self.assertRaises(UnsupportedVideoCodecConversion):
                operation.run(video["path"])
            pytest.skip("Video codec conversion not supported")

    @parameterized.expand(
        (
            (video, resolution)
            for video in VIDEO_FILES  # pylint: disable=undefined-variable
            for resolution in (
                [400, 300],
                [640, 480],
                [720, 480],
            )
        ),
        name_func=create_split_and_merge_with_resolution_change_test_name
    )
    @pytest.mark.slow
    def test_split_and_merge_with_resolution_change(self, video, resolution):
        source_codec = video["video_codec"]
        if not Container.is_supported(video['container'].value):
            pytest.skip("Target container not supported")
        if not video['container'].is_supported_video_codec(source_codec.value):
            pytest.skip("Target video codec not supported by the container")

        operation = SimulatedTranscodingOperation(
            task_executor=self,
            experiment_name="resolution change",
            resource_dir=self.RESOURCES,
            tmp_dir=self.tempdir)
        operation.attach_to_report_set(self._ffprobe_report_set)
        operation.request_resolution_change(resolution)
        operation.request_video_codec_change(source_codec)
        operation.request_container_change(video['container'])
        operation.exclude_from_diff(
            FfmpegIntegrationBase.ATTRIBUTES_NOT_PRESERVED_IN_CONVERSIONS)
        operation.enable_treating_missing_attributes_as_unchanged()

        filename = os.path.basename(video['path'])
        if filename in self._IGNORED_ATTRIBUTES_OF_BROKEN_FILE:
            operation.exclude_from_diff(
                self._IGNORED_ATTRIBUTES_OF_BROKEN_FILE[filename])

        if not Container.is_supported(video['container'].value):
            pytest.skip("Target container not supported")
        if not video['container'].is_supported_video_codec(source_codec.value):
            pytest.skip("Target video codec not supported by the container")

        if source_codec.can_convert(source_codec.value):
            pytest.skip("Transcoding is not possible for this file without"
                        "also changing the video codec.")

        try:
            validate_resolution(video["resolution"], resolution)
            (_input_report, _output_report, diff) = operation.run(video["path"])
            self.assertEqual(diff, [])
        except InvalidResolution:
            with self.assertRaises(InvalidResolution):
                operation.run(video["path"])
            pytest.skip("Target resolution not supported")

    @parameterized.expand(
        (
            (video, frame_rate)
            for video in VIDEO_FILES  # pylint: disable=undefined-variable
            for frame_rate in (
                FrameRate(1),
                FrameRate(25),
                FrameRate(30000, 1001),
                FrameRate(60),
            )
        ),
        name_func=create_split_and_merge_with_frame_rate_change_test_name
    )
    @pytest.mark.slow
    def test_split_and_merge_with_frame_rate_change(self, video, frame_rate):
        source_codec = video["video_codec"]
        operation = SimulatedTranscodingOperation(
            task_executor=self,
            experiment_name="frame rate change",
            resource_dir=self.RESOURCES,
            tmp_dir=self.tempdir,
            dont_include_in_option_description=["resolution", "video_codec"])
        operation.attach_to_report_set(self._ffprobe_report_set)
        operation.request_frame_rate_change(str(frame_rate))
        operation.request_video_codec_change(source_codec)
        operation.request_container_change(video['container'])
        operation.request_resolution_change(video["resolution"])
        operation.exclude_from_diff(
            FfmpegIntegrationBase.ATTRIBUTES_NOT_PRESERVED_IN_CONVERSIONS)
        operation.exclude_from_diff({'video': {'frame_count'}})
        fuzzy_rate = FuzzyDuration(frame_rate.to_float(), 0.5)
        operation.set_override('video', 'frame_rate', fuzzy_rate)
        operation.enable_treating_missing_attributes_as_unchanged()

        filename = os.path.basename(video['path'])
        if filename in self._IGNORED_ATTRIBUTES_OF_BROKEN_FILE:
            operation.exclude_from_diff(
                self._IGNORED_ATTRIBUTES_OF_BROKEN_FILE[filename])

        if not Container.is_supported(video['container'].value):
            pytest.skip("Target container not supported")
        if not video['container'].is_supported_video_codec(source_codec.value):
            pytest.skip("Target video codec not supported by the container")

        if source_codec.can_convert(source_codec.value):
            pytest.skip("Transcoding is not possible for this file without"
                        "also changing the video codec.")

        if frame_rate.normalized() in list_supported_frame_rates():
            (_input_report, _output_report, diff) = operation.run(video["path"])
            self.assertEqual(diff, [])
        else:
            with self.assertRaises(InvalidFrameRate):
                operation.run(video["path"])
            pytest.skip("Target frame rate not supported")

    @parameterized.expand(
        (
            (video, subtasks_count)
            for video in VIDEO_FILES  # pylint: disable=undefined-variable
            for subtasks_count in (1, 6, 10, video['key_frames'])
        ),
        name_func=create_split_and_merge_with_different_subtask_counts_test_name
    )
    @pytest.mark.slow
    def test_split_and_merge_with_different_subtask_counts(self,
                                                           video,
                                                           subtasks_count):
        source_codec = video["video_codec"]
        operation = SimulatedTranscodingOperation(
            task_executor=self,
            experiment_name="number of subtasks",
            resource_dir=self.RESOURCES,
            tmp_dir=self.tempdir,
            dont_include_in_option_description=["resolution", "video_codec"])
        operation.attach_to_report_set(self._ffprobe_report_set)
        operation.request_subtasks_count(subtasks_count)
        operation.request_video_codec_change(source_codec)
        operation.request_container_change(video['container'])
        operation.request_resolution_change(video["resolution"])
        operation.exclude_from_diff(
            FfmpegIntegrationBase.ATTRIBUTES_NOT_PRESERVED_IN_CONVERSIONS)
        operation.enable_treating_missing_attributes_as_unchanged()

        filename = os.path.basename(video['path'])
        if filename in self._IGNORED_ATTRIBUTES_OF_BROKEN_FILE:
            operation.exclude_from_diff(
                self._IGNORED_ATTRIBUTES_OF_BROKEN_FILE[filename])

        if not Container.is_supported(video['container'].value):
            pytest.skip("Target container not supported")
        if not video['container'].is_supported_video_codec(source_codec.value):
            pytest.skip("Target video codec not supported by the container")

        if source_codec.can_convert(source_codec.value):
            pytest.skip("Transcoding is not possible for this file without"
                        "also changing the video codec.")

        (_input_report, _output_report, diff) = operation.run(video["path"])
        self.assertEqual(diff, [])
