# -*- coding: utf-8 -*-
from Products.CMFCore.utils import getToolByName
from plone.app.event.dx.interfaces import IDXEvent
from plone.app.event.dx.behaviors import IEventAttendees
from plone.app.event.dx.behaviors import IEventContact
from plone.app.event.dx.behaviors import IEventLocation
from plone.app.event.portlets import portlet_events
from plone.dexterity.interfaces import IDexterityFTI
from plone.portlets import constants
from zope.annotation.interfaces import IAnnotatable
from zope.annotation.interfaces import IAnnotations
from zope.event import notify
from zope.component import queryUtility
from zope.component.hooks import getSite
from zope.lifecycleevent import ObjectModifiedEvent

import logging
log = logging.getLogger(__name__)

BEHAVIOR_LIST = [
    IEventAttendees,
    IEventContact,
    IEventLocation,
]


def enable_richtext_behavior(self):
    fti = queryUtility(IDexterityFTI, name="Event", default=None)
    if not fti:
        return
    behaviors = [it for it in fti.behaviors
                 if 'plone.app.event.dx.behaviors.IEventSummary' not in it]
    behaviors.extend([
        'plone.app.contenttypes.behaviors.richtext.IRichText',
    ])
    behaviors = tuple(set(behaviors))
    fti._updateProperty('behaviors', behaviors)


def upgrade_attribute_storage(context):
    portal = getSite()
    catalog = getToolByName(portal, 'portal_catalog')
    query = {}
    query['object_provides'] = IDXEvent.__identifier__
    results = catalog(**query)
    log.info('There are {0} in total, stating migration...'.format(
        len(results)))
    for result in results:
        try:
            event = result.getObject()
        except:
            log.warning(
                'Not possible to fetch event object from catalog result for '
                'item: {0}.'.format(result.getPath()))
            continue
        if not IAnnotatable.providedBy(event):
            log.warning(
                'The event at {0} does provide annotation capabilities, '
                'skipping.'.format(event.absolute_url()))
            continue
        annotations = IAnnotations(event)
        did_work = False
        for behavior in BEHAVIOR_LIST:
            for name in behavior.names():
                fullname = '{0}.{1}'.format(behavior.__identifier__, name)
                oldvalue = annotations.get(fullname, None)
                # Only write the old value if there is no new value yet
                if oldvalue and not getattr(event, name, None):
                    setattr(event, name, oldvalue)
                    did_work = True
        # The old IEventSummary behavior is gone, just look for the old name
        # inside the annotation storage
        oldvalue = annotations.get(
            'plone.app.event.dx.behaviors.IEventSummary.text', None)
        if oldvalue and not getattr(event, 'text', None):
            setattr(event, 'text', oldvalue)
            did_work = True
        if did_work:
            notify(ObjectModifiedEvent(event))
        log.debug('Handled event at {0}'.format(event.absolute_url()))


def remove_event_listing_settings(context):
    portal = getSite()
    actions = getToolByName(portal, 'portal_actions')
    ob = getattr(actions, 'object')
    if ob and getattr(ob, 'event_listing_settings', False):
        actions.object.manage_delObjects(['event_listing_settings', ])
        log.debug('Removed event_listing_settings from object actions.')


def migrate_events_portlets(context, path=None):
    """
    Fix missing attributes from old events portlets.

    Fixes a recursion error after upgrading:

    2019-04-29 18:10:09 ERROR imageportlet Error while determining renderer availability of portlet ('context' '/...' 'events'): maximum recursion depth exceeded
    Traceback (most recent call last):
      File "eggs/plone.portlets-2.3-py2.7.egg/plone/portlets/manager.py", line 117, in _lazyLoadPortlets
        isAvailable = renderer.available
      File "src/plone.app.event/plone/app/event/portlets/portlet_events.py", line 141, in available
        return self.data.count > 0 and len(self.events)
      File "src/plone.app.event/plone/app/event/portlets/portlet_events.py", line 154, in events
        if ICollection and ICollection.providedBy(self.search_base):
      File "src/plone.app.event/plone/app/event/portlets/portlet_events.py", line 122, in search_base
        if not self._search_base and self.data.search_base_uid:
      File "src/plone.app.event/plone/app/event/portlets/portlet_events.py", line 106, in _uid
        path = self.search_base
    ...
      File "src/plone.app.event/plone/app/event/portlets/portlet_events.py", line 122, in search_base
        if not self._search_base and self.data.search_base_uid:
      File "src/plone.app.event/plone/app/event/portlets/portlet_events.py", line 106, in _uid
        path = self.search_base
    RuntimeError: maximum recursion depth exceeded
    """
    annotations = IAnnotations(context, None)
    if annotations is None:
        return

    default_assignment_attrs = vars(portlet_events.Assignment())
    for mapping in annotations.get(
            constants.CONTEXT_ASSIGNMENT_KEY, {}).values():
        for assignment in mapping.values():
            if not isinstance(assignment, portlet_events.Assignment):
                continue

            attrs = vars(assignment)
            for attr, default in default_assignment_attrs.items():
                if attr not in attrs:
                    setattr(assignment, attr, default)


def migrate_portal_events_portlets(context):
    """
    Apply the events portlets missing attributes fix to all assignments.
    """
    portal = getSite()
    migrate_events_portlets(portal)
    portal.ZopeFindAndApply(
        portal, search_sub=1, apply_func=migrate_events_portlets)
