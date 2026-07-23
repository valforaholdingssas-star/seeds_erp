from rest_framework import serializers


class SettingPatchItemSerializer(serializers.Serializer):
    key = serializers.CharField()
    value = serializers.CharField(allow_blank=True, required=False, allow_null=True)


class SettingPatchSerializer(serializers.Serializer):
    settings = SettingPatchItemSerializer(many=True)
