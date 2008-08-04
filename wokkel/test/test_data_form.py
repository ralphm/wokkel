# Copyright (c) 2003-2008 Ralph Meijer
# See LICENSE for details.

"""
Tests for {wokkel.data_form}.
"""

from twisted.trial import unittest
from twisted.words.xish import domish

from wokkel.data_form import Field, Form, Option, FieldNameRequiredError

NS_X_DATA = 'jabber:x:data'



class OptionTest(unittest.TestCase):
    """
    Tests for L{Option}.
    """

    def test_toElement(self):
        option = Option('value', 'label')
        element = option.toElement()
        self.assertEquals('option', element.name)
        self.assertEquals(NS_X_DATA, element.uri)
        self.assertEquals('label', element['label'])
        self.assertEquals('value', element.value.name)
        self.assertEquals(NS_X_DATA, element.value.uri)
        self.assertEquals('value', unicode(element.value))



class FieldTest(unittest.TestCase):
    """
    Tests for L{Field}.
    """

    def test_basic(self):
        field = Field(var='test')
        self.assertEqual('text-single', field.fieldType)
        self.assertEqual('test', field.var)

        element = field.toElement()

        self.assertTrue(domish.IElement.providedBy(element))
        self.assertEquals('field', element.name)
        self.assertEquals(NS_X_DATA, element.uri)
        self.assertEquals('text-single', element['type'])
        self.assertEquals('test', element['var'])
        self.assertEquals([], element.children)


    def test_noFieldName(self):
        field = Field()
        self.assertRaises(FieldNameRequiredError, field.toElement)


    def test_fromElementType(self):
        element = domish.Element((NS_X_DATA, 'field'))
        element['type'] = 'fixed'
        field = Field.fromElement(element)
        self.assertEquals('fixed', field.fieldType)


    def test_fromElementNoType(self):
        element = domish.Element((NS_X_DATA, 'field'))
        field = Field.fromElement(element)
        self.assertEquals(None, field.fieldType)


    def test_fromElementValue(self):
        element = domish.Element((NS_X_DATA, 'field'))
        element.addElement("value", content="text")
        field = Field.fromElement(element)
        self.assertEquals('text', field.value)



class FormTest(unittest.TestCase):
    """
    Tests for L{Form}.
    """

    def test_formType(self):
        """
        A form has a type.
        """

        form = Form('result')
        self.assertEqual('result', form.formType)

    def test_toElement(self):
        """
        The toElement method returns a form's DOM representation.
        """
        form = Form('result')
        element = form.toElement()

        self.assertTrue(domish.IElement.providedBy(element))
        self.assertEquals('x', element.name)
        self.assertEquals(NS_X_DATA, element.uri)
        self.assertEquals('result', element['type'])
        self.assertEquals([], element.children)


    def test_fromElement(self):
        """
        The fromElement static method creates a L{Form} from a L{DOM.
        """
        element = domish.Element((NS_X_DATA, 'x'))
        element['type'] = 'result'
        form = Form.fromElement(element)

        self.assertEquals('result', form.formType)
        self.assertEquals(None, form.title)
        self.assertEquals([], form.instructions)
        self.assertEquals({}, form.fields)


    def test_fromElementInvalidElementName(self):
        """
        Bail if the passed element does not have the correct name.
        """
        element = domish.Element((NS_X_DATA, 'form'))
        self.assertRaises(Exception, Form.fromElement, element)


    def test_fromElementInvalidElementURI(self):
        """
        Bail if the passed element does not have the correct namespace.
        """
        element = domish.Element(('myns', 'x'))
        self.assertRaises(Exception, Form.fromElement, element)


    def test_fromElementTitle(self):
        element = domish.Element((NS_X_DATA, 'x'))
        element.addElement('title', content='My title')
        form = Form.fromElement(element)

        self.assertEquals('My title', form.title)


    def test_fromElementInstructions(self):
        element = domish.Element((NS_X_DATA, 'x'))
        element.addElement('instructions', content='instruction')
        form = Form.fromElement(element)

        self.assertEquals(['instruction'], form.instructions)

    def test_fromElementInstructions2(self):
        element = domish.Element((NS_X_DATA, 'x'))
        element.addElement('instructions', content='instruction 1')
        element.addElement('instructions', content='instruction 2')
        form = Form.fromElement(element)

        self.assertEquals(['instruction 1', 'instruction 2'], form.instructions)


    def test_fromElementOneField(self):
        element = domish.Element((NS_X_DATA, 'x'))
        element.addElement('field')
        form = Form.fromElement(element)

        self.assertEquals(1, len(form.fieldList))
        self.assertNotIn('field', form.fields)


    def test_fromElementTwoFields(self):
        element = domish.Element((NS_X_DATA, 'x'))
        element.addElement('field')['var'] = 'field1'
        element.addElement('field')['var'] = 'field2'
        form = Form.fromElement(element)

        self.assertEquals(2, len(form.fieldList))
        self.assertIn('field1', form.fields)
        self.assertEquals('field1', form.fieldList[0].var)
        self.assertIn('field2', form.fields)
        self.assertEquals('field2', form.fieldList[1].var)
