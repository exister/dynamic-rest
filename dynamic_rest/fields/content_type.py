import traceback

from dynamic_rest.fields.common import WithRelationalFieldMixin
from dynamic_rest.fields.fields import DynamicField
from dynamic_rest.routers import DynamicRouter
from dynamic_rest.tagged import TaggedDict


class DynamicGenericRelationField(
    WithRelationalFieldMixin,
    DynamicField
):

    def __init__(self, embed=False, *args, **kwargs):
        super(DynamicGenericRelationField, self).__init__(*args, **kwargs)
        self.embed = embed
        self.read_only = True

    def bind(self, field_name, parent):
        super(DynamicGenericRelationField, self).bind(field_name, parent)

        source = self.source or field_name

        # Inject `requires` so required fields get prefetched properly.
        # TODO: It seems like we should be able to require the type and
        #       id fields, but that seems to conflict with some internal
        #       Django magic. Disabling `.only()` by requiring '*' seem
        #       to work more reliably...
        self.requires = [
            source + '.*',
            '*'
        ]

    def id_only(self):
        # For DynamicRelationFields, id_only() is a serializer responsibility
        # but for generic relations, we want IDs to be represented differently
        # and that is a field-level concern, not an object-level concern,
        # so we handle it here.
        request_fields = self._get_request_fields_from_parent()
        return request_fields is True

    def get_pk_object(self, type_key, id_value):
        return {
            'type': type_key,
            'id': id_value
        }

    def to_representation(self, instance):
        try:
            # Find serializer for the instance
            serializer_class = DynamicRouter.get_canonical_serializer(
                resource_key=None,
                instance=instance
            )
            if not serializer_class:
                # Can't find canonical serializer! For now, just return
                # object name and ID, and hope the client knows what to do
                # with it.
                return self.get_pk_object(
                    instance._meta.object_name,
                    instance.pk
                )

            # We want the pk to be represented as an object with type,
            # rather than just the ID.
            pk_value = self.get_pk_object(
                serializer_class().get_plural_name(),
                instance.pk
            )
            if self.id_only():
                return pk_value

            # Serialize the object. Note that request_fields is set, which
            # means field inclusion/exclusion *may* work. Yolo!
            r = serializer_class(
                dynamic=True,
                request_fields=self._get_request_fields_from_parent(),
                context=self.context,
                embed=self.embed
            ).to_representation(
                instance
            )

            # Pass pk object that contains type and ID to TaggedDict object
            # so that Processor can use it when the field gets sideloaded.
            if isinstance(r, TaggedDict):
                r.pk_value = pk_value
            return r
        except:
            traceback.print_exc()
            return None
