=================
Upgrading to 1.0
=================

Errors
-------

If you see this error when trying to delete a stack using a newer version of stacker::

	You are attempting to destroy `your_stack` which was created using 
	an older version of stacker. Please first updated all your stacks using
	`stacker build` so that they can be adjusted for the new version. More 
	information on this issue here.

This error can be fixed simply by calling `stacker build` this will automatically update 
the stacks to use the new event system. 

When calling `stacker build` for the first time after the upgrade it will upgrade every 
stack even if you have not made any changes to the template or the configuration file. This 
is expected, behind the scenes stacker is just adding the `NotificationARNs parameter` to the 
stacks.