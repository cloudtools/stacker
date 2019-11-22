from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import object
import collections
import json
import logging

from stacker.config import Config
from .exceptions import (PersistentGraphCannotLock,
                         PersistentGraphCannotUnlock,
                         PersistentGraphLocked,
                         PersistentGraphLockCodeMissmatch,
                         PersistentGraphUnlocked)
from .plan import Graph
from .session_cache import get_session
from .stack import Stack
from .target import Target
from .util import ensure_s3_bucket

logger = logging.getLogger(__name__)


DEFAULT_NAMESPACE_DELIMITER = "-"
DEFAULT_TEMPLATE_INDENT = 4


def get_fqn(base_fqn, delimiter, name=None):
    """Return the fully qualified name of an object within this context.

    If the name passed already appears to be a fully qualified name, it
    will be returned with no further processing.

    """
    if name and name.startswith("%s%s" % (base_fqn, delimiter)):
        return name

    return delimiter.join([_f for _f in [base_fqn, name] if _f])


class Context(object):
    """The context under which the current stacks are being executed.

    The stacker Context is responsible for translating the values passed in via
    the command line and specified in the config to `Stack` objects.

    Args:
        environment (dict): A dictionary used to pass in information about
            the environment. Useful for templating.
        stack_names (list): A list of stack_names to operate on. If not passed,
            usually all stacks defined in the config will be operated on.
        config (:class:`stacker.config.Config`): The stacker configuration
            being operated on.
        region (str): Name of an AWS region if provided as a CLI argument.
        force_stacks (list): A list of stacks to force work on. Used to work
            on locked stacks.

    """

    def __init__(self, environment=None,
                 stack_names=None,
                 config=None,
                 region=None,
                 force_stacks=None):
        self._bucket_name = None
        self._persistent_graph = None
        self._persistent_graph_lock_code = None
        self._persistent_graph_lock_tag = 'stacker_lock_code'
        self._s3_bucket_verified = None
        self._upload_to_s3 = None
        self.bucket_region = config.stacker_bucket_region or region
        self.config = config or Config()
        self.environment = environment
        self.force_stacks = force_stacks or []
        self.hook_data = {}
        self.s3_conn = get_session(self.bucket_region).client('s3')
        self.stack_names = stack_names or []

    @property
    def _base_fqn(self):
        return self.namespace.replace(".", "-").lower()

    @property
    def _persistent_graph_tags(self):
        """Cached dict of tags on the persistent graph object.

        Returns:
            (Dict[str, str])

        """
        try:
            return {t['Key']: t['Value'] for t in
                    self.s3_conn.get_object_tagging(
                    **self.persistent_graph_location
                    ).get('TagSet', {})}
        except self.s3_conn.exceptions.NoSuchKey:
            logger.debug('Persistant graph object does not exist in S3; '
                         'could not get tags')
            return {}

    @property
    def namespace(self):
        return self.config.namespace

    @property
    def namespace_delimiter(self):
        delimiter = self.config.namespace_delimiter
        if delimiter is not None:
            return delimiter
        return DEFAULT_NAMESPACE_DELIMITER

    @property
    def template_indent(self):
        indent = self.config.template_indent
        if indent is not None:
            return int(indent)
        return DEFAULT_TEMPLATE_INDENT

    @property
    def bucket_name(self):
        """Stacker bucket name."""
        if not self.upload_to_s3:
            return None
        if not self._bucket_name:
            self._bucket_name = self.config.stacker_bucket \
                or "stacker-%s" % (self.get_fqn())
        return self._bucket_name

    @property
    def mappings(self):
        return self.config.mappings or {}

    @property
    def persistent_graph(self):
        """Persistent graph object if one is to be used.

        Will create an "empty" object in S3 if one is not found.

        Returns:
            (:class:`stacker.plan.Graph`)

        """
        if not self.persistent_graph_location:
            return None

        content = '{}'

        if not self._persistent_graph:
            if self.s3_bucket_verified:
                try:
                    logger.debug('Getting persistent graph from s3:\n%s',
                                 json.dumps(self.persistent_graph_location,
                                            indent=4))
                    content = self.s3_conn.get_object(
                        ResponseContentType='application/json',
                        **self.persistent_graph_location
                    )['Body'].read().decode('utf-8')
                except self.s3_conn.exceptions.NoSuchKey:
                    logger.info('Persistant graph object does not exist '
                                'in S3; creating one now.')
                    self.s3_conn.put_object(
                        Body=content,
                        ServerSideEncryption='AES256',
                        ACL='bucket-owner-full-control',
                        ContentType='application/json',
                        **self.persistent_graph_location
                    )
            self.persistent_graph = json.loads(content)

        return self._persistent_graph

    @persistent_graph.setter
    def persistent_graph(self, graph_dict):
        """Load a persistent graph dict as a :class:`stacker.plan.Graph`."""
        self._persistent_graph = Graph.from_dict(graph_dict, self)

    @property
    def persistent_graph_location(self):
        """Location of the persistent graph in s3.

        Returns:
            (Dict[str, str]) Bucket and Key for the object in S3.

        """
        if not self.upload_to_s3 or not self.config.persistent_graph_key:
            return {}

        return {
            'Bucket': self.bucket_name,
            'Key': 'persistent_graphs/{namespace}/{key}'.format(
                namespace=self.config.namespace,
                key=(self.config.persistent_graph_key + '.json' if not
                     self.config.persistent_graph_key.endswith('.json')
                     else self.config.persistent_graph_key)
            )
        }

    @property
    def persistent_graph_lock_code(self):
        """Code used to lock the persistent graph S3 object.

        Returns:
            (Optional[str])

        """
        if not self._persistent_graph_lock_code:
            self._persistent_graph_lock_code = self._persistent_graph_tags.get(
                self._persistent_graph_lock_tag
            )
        return self._persistent_graph_lock_code

    @property
    def persistent_graph_locked(self):
        """Check if persistent graph is locked.

        Returns:
            (bool)

        """
        if not self.persistent_graph:
            return False
        if not self.persistent_graph_lock_code:
            return False
        return True

    @property
    def s3_bucket_verified(self):
        """Check Stacker bucket exists and you have access.

        If the Stacker bucket does not exist, will try to create one.

        Returns:
            (bool)

        """
        if not self._s3_bucket_verified and self.bucket_name:
            ensure_s3_bucket(self.s3_conn,
                             self.bucket_name,
                             self.bucket_region,
                             persist_graph=(True if
                                            self.persistent_graph_location
                                            else False))
            self._s3_bucket_verified = True
        return self._s3_bucket_verified

    @property
    def tags(self):
        tags = self.config.tags
        if tags is not None:
            return tags
        if self.namespace:
            return {"stacker_namespace": self.namespace}
        return {}

    @property
    def upload_to_s3(self):
        """Check if S3 should be used for caching/persistent graph.

        Returns:
            (bool)

        """
        if not self._upload_to_s3:
            # Don't upload stack templates to S3 if `stacker_bucket` is
            # explicitly set to an empty string.
            if self.config.stacker_bucket == '':
                logger.debug("Not uploading to s3 because `stacker_bucket` "
                             "is explicitly set to an empty string")
                return False

            # If no namespace is specificied, and there's no explicit
            # stacker bucket specified, don't upload to s3. This makes
            # sense because we can't realistically auto generate a stacker
            # bucket name in this case.
            if not self.namespace and not self.config.stacker_bucket:
                logger.debug("Not uploading to s3 because there is no "
                             "namespace set, and no stacker_bucket set")
                return False

        return True

    def _get_stack_definitions(self):
        return self.config.stacks

    def get_targets(self):
        """Returns the named targets that are specified in the config.

        Returns:
            list: a list of :class:`stacker.target.Target` objects

        """
        if not hasattr(self, "_targets"):
            targets = []
            for target_def in self.config.targets or []:
                target = Target(target_def)
                targets.append(target)
            self._targets = targets
        return self._targets

    def get_stacks(self):
        """Get the stacks for the current action.

        Handles configuring the :class:`stacker.stack.Stack` objects that will
        be used in the current action.

        Returns:
            list: a list of :class:`stacker.stack.Stack` objects

        """
        if not hasattr(self, "_stacks"):
            stacks = []
            definitions = self._get_stack_definitions()
            for stack_def in definitions:
                stack = Stack(
                    definition=stack_def,
                    context=self,
                    mappings=self.mappings,
                    force=stack_def.name in self.force_stacks,
                    locked=stack_def.locked,
                    enabled=stack_def.enabled,
                    protected=stack_def.protected,
                )
                stacks.append(stack)
            self._stacks = stacks
        return self._stacks

    def get_stack(self, name):
        for stack in self.get_stacks():
            if stack.name == name:
                return stack

    def get_stacks_dict(self):
        return dict((stack.fqn, stack) for stack in self.get_stacks())

    def get_fqn(self, name=None):
        """Return the fully qualified name of an object within this context.

        If the name passed already appears to be a fully qualified name, it
        will be returned with no further processing.

        """
        return get_fqn(self._base_fqn, self.namespace_delimiter, name)

    def lock_persistent_graph(self, lock_code):
        """Locks the persistent graph in s3.

        Args:
            lock_code (str): The code that will be used to lock the S3 object.

        Raises:
            :class:`stacker.exceptions.PersistentGraphLocked`
            :class:`stacker.exceptions.PersistentGraphCannotLock`

        """
        if not self.persistent_graph:
            return

        if self.persistent_graph_locked:
            raise PersistentGraphLocked

        try:
            self.s3_conn.put_object_tagging(
                Tagging={'TagSet': [
                    {'Key': self._persistent_graph_lock_tag,
                     'Value': lock_code}
                ]},
                **self.persistent_graph_location
            )
            logger.info('Locked persistent graph "%s" with lock ID "%s".',
                        '/'.join([self.persistent_graph_location['Bucket'],
                                  self.persistent_graph_location['Key']]),
                        lock_code)
        except self.s3_conn.exceptions.NoSuchKey:
            raise PersistentGraphCannotLock('s3 object does not exist')

    def put_persistent_graph(self, lock_code):
        """Upload persistent graph to s3.

        Args:
            lock_code (str): The code that will be used to lock the S3 object.

        Raises:
            :class:`stacker.exceptions.PersistentGraphUnlocked`
            :class:`stacker.exceptions.PersistentGraphLockCodeMissmatch`

        """
        if not self.persistent_graph:
            return

        if not self.persistent_graph_locked:
            raise PersistentGraphUnlocked(
                reason='It must be locked by the current session to be '
                       'updated.'
            )

        if self.persistent_graph_lock_code != lock_code:
            raise PersistentGraphLockCodeMissmatch(
                lock_code, self.persistent_graph_lock_code
            )

        if not self.persistent_graph.to_dict():
            self.s3_conn.delete_object(**self.persistent_graph_location)
            logger.debug('Removed empty persistent graph object from S3')
            return

        self.s3_conn.put_object(
            Body=self.persistent_graph.dumps(4),
            ServerSideEncryption='AES256',
            ACL='bucket-owner-full-control',
            ContentType='application/json',
            Tagging='{}={}'.format(self._persistent_graph_lock_tag,
                                   lock_code),
            **self.persistent_graph_location
        )
        logger.debug('Persistent graph updated:\n%s',
                     self.persistent_graph.dumps(indent=4))

    def set_hook_data(self, key, data):
        """Set hook data for the given key.

        Args:
            key(str): The key to store the hook data in.
            data(:class:`collections.Mapping`): A dictionary of data to store,
                as returned from a hook.
        """

        if not isinstance(data, collections.Mapping):
            raise ValueError("Hook (key: %s) data must be an instance of "
                             "collections.Mapping (a dictionary for "
                             "example)." % key)

        if key in self.hook_data:
            raise KeyError("Hook data for key %s already exists, each hook "
                           "must have a unique data_key.", key)

        self.hook_data[key] = data

    def unlock_persistent_graph(self, lock_code):
        """Unlocks the persistent graph in s3.

        Args:
            lock_code (str): The code that will be used to lock the S3 object.

        Raises:
            :class:`stacker.exceptions.PersistentGraphCannotUnlock`

        """
        if not self.persistent_graph:
            return

        logger.debug('Unlocking persistent graph "%s".',
                     self.persistent_graph_location)

        if not self.persistent_graph_locked:
            raise PersistentGraphCannotUnlock(PersistentGraphUnlocked(
                reason='It must be locked by the current session to be '
                       'unlocked.'
            ))

        if self.persistent_graph_lock_code == lock_code:
            try:
                self.s3_conn.delete_object_tagging(
                    **self.persistent_graph_location
                )
            except self.s3_conn.exceptions.NoSuchKey:
                pass
            self._persistent_graph_lock_code = None
            logger.info('Unlocked persistent graph "%s".',
                        '/'.join([self.persistent_graph_location['Bucket'],
                                  self.persistent_graph_location['Key']]))
            return True
        raise PersistentGraphCannotUnlock(
            PersistentGraphLockCodeMissmatch(
                lock_code,
                self.persistent_graph_lock_code
            )
        )
