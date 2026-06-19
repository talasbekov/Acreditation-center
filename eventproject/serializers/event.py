from rest_framework import serializers
from eventproject.models import Event, Category

class CategorySerializer(serializers.ModelSerializer):
    attendee_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "attendee_count"]

    def get_attendee_count(self, obj):
        # Используем related_name="attendees" из модели Attendee
        return obj.attendees.count()

class EventSerializer(serializers.ModelSerializer):
    categories = CategorySerializer(many=True, read_only=True)

    class Meta:
        model = Event
        fields = ["id", "title", "start_date", "end_date", "description", "categories", "created_at"]
        read_only_fields = ["id", "created_at"]
