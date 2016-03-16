"""v8coder - a module for reading/writing v8 in its native format"""

from structio import StructIO
from enum import Enum
import varint


class SerializationTag(Enum):
    INVALID = '!'
    PADDING = '@'
    UNDEFINED = '_'
    NULL = '0'
    TRUE = 'T'
    FALSE = 'F'
    STRING = 'S'
    STRING_UCHAR = 'c'
    INT32 = 'I'
    UINT32 = 'U'
    DATE = 'D'
    MESSAGE_PORT = 'M'
    NUMBER = 'N'
    BLOB = 'b'
    BLOB_INDEX = 'i'
    FILE = 'f'
    FILE_INDEX = 'f'
    DOM_FILE_SYSTEM = 'd'
    FILE_LIST = 'l'
    FILE_LIST_INDEX = 'L'
    IMAGE_DATA = '#'
    OBJECT = '{'
    SPARSE_ARRAY = '@'
    DENSE_ARRAY = '$'
    REG_EXP = 'R'
    ARRAY_BUFFER = 'B'
    ARRAY_BUFFER_TRANSFER = 't'
    IMAGE_BITMAP_TRANSFER = 'G'
    ARRAY_BUFFER_VIEW = 'V'
    SHARED_ARRAY_BUFFER_TRANSFER = 'u'
    CRYPTO_KEY = 'K'
    OBJECT_REFERENCE = '^'
    GENERATE_FRESH_OBJECT = 'o'
    GENERATE_FRESH_SPARSE_ARRAY = 'a'
    GENERATE_FRESH_DENSE_ARRAY = 'A'
    REFERENCE_COUNT = '?'
    STRING_OBJECT = 's'
    NUMBER_OBJECT = 'n'
    TRUE_OBJECT = 'y'
    FALSE_OBJECT = 'x'
    COMPOSITOR_PROXY = 'C'
    MAP = ':'
    SET = ','
    GENERATE_FRESH_MAP = ';'
    GENERATE_FRESH_SET = '\''
    VERSION = '\xff'

class ArrayBufferViewSubtag(Enum):
    BYTE_ARRAY = 'b'
    UNSIGNED_BYTE_ARRAY = 'B'
    UNSIGNED_BYTE_CLAMPED_ARRAY = 'C'
    SHORT_ARRAY = 'w'
    UNSIGNED_SHORT_ARRAY = 'W'
    INT_ARRAY = 'd'
    UNSIGNED_INT_ARRAY = 'D'
    FLOAT_ARRAY = 'f'
    DOUBLE_ARRAY = 'F'
    DATA_VIEW = '?'


class ZigZag(object):
    @staticmethod
    def encode(value):
        if value & (1 << 31):
            value = ((~value) << 1) + 1
        else:
            value <<= 1
        return value

    @staticmethod
    def decode(value):
        if value & 1:
            value = ~(value >> 1)
        else:
            value >>= 1
        return value


class SwapBytes(object):
    @staticmethod
    def encode(data):
        result = ''
        i = 0
        for i in xrange(0, len(data), 2):
            b = data[i:i+2]
            if len(b) == 2:
                result += b[1] + b[0]
            else:
                result += SerializationTag.PADDING.value + b[0]
        return result

    @staticmethod
    def decode(data):
        result = ''
        i = 0
        for i in xrange(0, len(data), 2):
            b = data[i:i+2]
            assert len(b) == 2, "Unexpected odd number of bytes while decoding"
            result += b[1] + b[0]

        if result[-1] == SerializationTag.PADDING.value:
            return result[:-1]
        return result


NOOP_TAGS = set([
    SerializationTag.PADDING,
    SerializationTag.GENERATE_FRESH_OBJECT,
])
VARINT_TAGS = set([
    SerializationTag.REFERENCE_COUNT,
    SerializationTag.OBJECT,
])


class Reader(StructIO):
    def read_tag(self):
        tag = self.read(1)
        return SerializationTag(tag)

    def read_varint(self):
        return varint.decode_stream(self)

    def read_token(self):
        tag = self.read_tag()
        if tag in NOOP_TAGS:
            return (tag, None)
        elif tag in VARINT_TAGS:
            return (tag, self.read_varint())
        elif tag == SerializationTag.VERSION:
            value = self.read_varint()
            assert value <= 9, (value, "0x%x"%value)
            return (tag, value)
        elif tag == SerializationTag.ARRAY_BUFFER:
            buflen = self.read_varint()
            return (tag, self.read(buflen))
        elif tag == SerializationTag.STRING:
            # TODO: try reading as uint32 first
            strlen = self.read_varint()
            result = self.read(strlen)
            return (tag, result)
        elif tag == SerializationTag.DATE:
            return (tag, self.read_double())
        elif tag == SerializationTag.INT32:
            result = self.read_varint()
            return (tag, ZigZag.decode(result))
        elif tag == SerializationTag.ARRAY_BUFFER_VIEW:
            subtag = ArrayBufferViewSubtag(self.read(1))
            offset = self.read_varint()
            length = self.read_varint()
            return (tag, (subtag, offset, length))
        else:
            raise NotImplementedError(
                'Unimplemented Tag, %s' %
                (tag.name),
            )

class Writer(StructIO):
    def write_tag(self, tag):
        self.write(SerializationTag(tag).value)

    def write_varint(self, value):
        self.write(varint.encode(value))

    def write_token(self, tag, *token_args):
        if tag in NOOP_TAGS:
            self.write_tag(tag)
        elif tag == SerializationTag.VERSION:
            value, = token_args
            self.write_tag(tag)
            self.write_varint(value)
        elif tag in VARINT_TAGS:
            value, = token_args
            self.write_tag(tag)
            self.write_varint(value)
        elif tag == SerializationTag.ARRAY_BUFFER:
            value, = token_args
            self.write_tag(tag)
            self.write_varint(len(value))
            self.write(value)
        elif tag == SerializationTag.STRING:
            value, = token_args
            self.write_tag(tag)
            assert len(value) > 1, "Short STRING not Implemented"
            self.write_varint(len(value))
            self.write(value)
        elif tag == SerializationTag.DATE:
            value, = token_args
            self.write_double(value)
        elif tag == SerializationTag.INT32:
            value, = token_args
            value = ZigZag.encode(value)
            self.write_varint(value)
        elif tag == SerializationTag.ARRAY_BUFFER_VIEW:
            subtag, offset, length = token_args
            subtag = ArrayBufferViewSubtag(subtag)
            self.write(subtag.value)
            self.write_varint(offset)
            self.write_varint(length)
        else:
            raise NotImplementedError(
                'Unimplemented Tag, %s' %
                (tag.name),
            )
